"""Corporate Income Tax Return: the Körperschaftsteuererklärung of a GmbH or UG for one Veranlagungszeitraum, with the
Erklärung zur gesonderten Feststellung des steuerlichen Einlagekontos (KSt 1, Anlagen GK, ZVE, WA, Verluste and Z,
KSt 1 F; § 31 Absatz 1 and § 27 Absatz 2 Satz 4 KStG).

The document lives on the base of the annual documents (steuerbote/steuerbote/annual_filing.py, docs/jahresmeldungen.md):
its status, Berechnen with the corrections and lines by hand, the findings, the filing, the Berichtigung and the
transmission through ERiC are those of AnnualFiling and Transmittable. This controller gives it the Körperschaftsteuer:

- Berechnen (compute) reads the profit and loss account of the Wirtschaftsjahr, the Vorauszahlungen booked, the Income
  Tax Mapping and the Annual Filing Settings (steuerbote/income_tax_sources.py) and runs the core in steuerbote/kst
  through bridge.py, with the lines by hand, the corrections and the tables of the return; on the lines as filed it
  checks the rules of the Jahresdokumentation E30 that Steuerbote checks itself (check_reported).
- Anlage GK line 11 comes from the E-Bilanz of the year the return names (electronic_balance_sheet): its
  Jahresüberschuss, under HGBM that of the Handelsbilanz with the Überleitung to the Steuerbilanz (contract of stage
  3, 3.3). Berechnen names the E-Bilanz it takes: the one named while it is calculated or filed and not replaced,
  else the newest such E-Bilanz of the company and year; without one, line 11 is the Jahresüberschuss of the books.
  KSt 1 F lines 17 and 18 come from the E-Bilanz filed for the previous year, else from the return by hand.
- A save takes the corrections and lines by hand of the lines of the books and of those left to hand, the tables of
  the return and its statements, refuses a correction where the computation derives the line, and fills the columns
  of the § 8b results from the holdings register. A change of anything Berechnen reads leaves a calculated return
  Berechnet until Berechnen checks it again.
- The deadline is the day Offene Fristen lists for the Körperschaftsteuererklärung of the year (annual_deadline in
  steuerbote/steuerbote/deadlines.py): § 149 Absatz 2 to 4 AO with the Steuerberatung and the Vorabanforderung of the
  Annual Filing Settings.
- Rückstellungen vorschlagen (propose_provisions) makes a draft Journal Entry of the provisions for Körperschaftsteuer,
  Solidaritätszuschlag and Gewerbesteuer of steuerbote.kst.provisions, the Solidaritätszuschlag in the provision of
  the Körperschaftsteuer, which the company checks and submits: Steuerbote posts nothing (decision 6.3 and adopted
  answer Q8 of the contract of stage 3). Every tax on income is added back in Anlage GK lines 81 to 84, so the zu
  versteuerndes Einkommen is the same once they are posted.
- Prüfen, Testsenden and Senden go through ERiC in the Datenart KSt of the year (datenart.kst) with the Nutzdaten E30
  of steuerbote/elster/kst_xml.py, in the simulation until the Hersteller-ID exists, and for real once ERiC brings the
  plugin of the year. Mein ELSTER imports no Körperschaftsteuererklärung: it is typed in there from the print format
  „Körperschaftsteuererklärung“, and the filing is noted with „In Mein ELSTER abgegeben“.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from steuerbote import ebilanz_sources, income_tax_sources
from steuerbote.deadlines import Kind
from steuerbote.ebilanz.positions import euro
from steuerbote.elster import kst_xml
from steuerbote.eric import datenart as eric_datenart
from steuerbote.jahresmeldung import findings as annual_findings
from steuerbote.jahresmeldung.findings import Finding, Severity
from steuerbote.jahresmeldung.lifecycle import Event
from steuerbote.kst import provisions
from steuerbote.kst.categories import Mapping
from steuerbote.kst.form import catalogue_for
from steuerbote.ledger import account_names
from steuerbote.steuerbote import guards
from steuerbote.steuerbote.annual_filing import FINDINGS_TABLE, RECALCULATE, AnnualFiling, Calculation
from steuerbote.steuerbote.deadlines import annual_deadline
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge, layout
from steuerbote.steuerbote.doctype.elster_transmission.transmission import Transmittable
from steuerbote.steuerbote.doctype.trade_tax_return import bridge as trade_tax_bridge
from steuerbote.steuerbote.doctype.vat_return.vat_return import SiteFigures
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors
from steuerbote.steuerbote.recorded_vouchers import ProposedJournalEntries
from steuerbote.ustva.years import UnknownYearError

DOCTYPE = "Corporate Income Tax Return"
JOURNAL_ENTRY = "Journal Entry"
VORGANG = "01"
INPUT_TABLES = ("holding_results", "credits", "donations", "distributions", "contributions")
INPUT_FIELDS = (
	"electronic_balance_sheet",
	"supplement_key",
	"supplement_text",
	"shareholder_contracts",
	"carry_back_chosen",
	"loss_carry_back",
	"turnover_and_wages_given",
	"turnover_and_wages",
	"previous_equity",
	"previous_nominal_capital",
)
"""What Berechnen reads of the return besides its lines."""
HOLDING_COLUMNS = ("percent_on_1_january", "percent_at_start_of_ez", "exemption")
PROVISIONS_DIFFER = "KST-RUECKSTELLUNG-DIFFERENZ"
"""The columns of the § 8b results that a save fills from the holdings register."""


class CorporateIncomeTaxReturn(ProposedJournalEntries, AnnualFiling, Transmittable, Document):
	PROPOSED_ENTRIES = ("provisions_entry",)
	LINES = "lines"
	LINE_COLUMNS = bridge.LINE_COLUMNS
	CALCULATED_FIELDS = (
		"net_income",
		"business_income",
		"sum_of_income",
		"total_income",
		"zve",
		"kst",
		"solz",
		"capital_gains_tax_credit",
		"solz_credit",
		"kst_prepayments",
		"solz_prepayments",
		"kst_balance",
		"solz_balance",
		"einlagekonto",
	)

	# The hooks of the base.

	def compute(self) -> Calculation:
		"""Berechnen: the Körperschaftsteuer of the year from the sources and the return, Anlage GK line 11 from the
		E-Bilanz it takes and names."""
		self.electronic_balance_sheet = ebilanz_sources.ebilanz_for_income_tax(
			self.company, cint(self.year), self.electronic_balance_sheet
		)
		computation = self.computation()
		found = (*computation.findings, *self.provision_findings(computation))
		return Calculation(lines=computation.lines, values=computation.values, findings=found)

	def provision_findings(self, computation: bridge.Computation) -> list[Finding]:
		"""A hint where the books hold provisions for the Körperschaftsteuer and the Solidaritätszuschlag of the year that
		are not their balances, as after a posting since Rückstellungen vorschlagen (§ 249 Abs. 1 Satz 1 HGB)."""
		posted = self.posted_provisions()
		if not posted or not any(posted.values()):
			return []
		found = provisions.differences(computation.result, None, posted)
		if not found:
			return []
		parts = ", ".join(
			f"{tax} {euro(abs(difference))} {'mehr' if difference > 0 else 'weniger'} als gebucht"
			for tax, difference in found.items()
		)
		return [
			Finding(
				PROVISIONS_DIFFER,
				Severity.HINT,
				_(
					"The books hold provisions for the taxes of {0} that differ from the taxes of this return: {1}. Rückstellungen vorschlagen proposes the difference (§ 249 Abs. 1 Satz 1 HGB)."
				).format(cint(self.year), parts),
			)
		]

	def posted_provisions(self) -> dict[provisions.Tax, Decimal] | None:
		"""What the books of the Wirtschaftsjahr hold of the provision or the claim to a refund of each tax, a provision
		positive; None for a chart without the accounts of the provisions."""
		accounts = provisions.ACCOUNTS.get(income_tax_sources.mapping(self.company).chart)
		if accounts is None:
			return None
		postings = income_tax_sources.tax_postings(
			self.company,
			getdate(self.from_date),
			getdate(self.to_date),
			accounts,
			income_tax_sources.commercial_finance_book(self.company),
		)
		_booked, posted = bridge.booked_taxes(postings, accounts)
		return {tax: posted[key] for tax, key in zip(provisions.Tax, bridge.TAX_KEYS, strict=True)}

	def check_reported(self, lines) -> list[Finding]:
		"""The rules of the Jahresdokumentation E30 that Steuerbote checks itself, on the Vordrucke the return files with
		its lines as Berechnen keeps them."""
		year = self._year()
		with core_errors():
			filed = bridge.filed_vordrucke(self._return(lines), lines, self.settings())
		return bridge.rule_findings(year, filed, _)

	def compute_deadline(self) -> date | None:
		"""The day the return is due, as Offene Fristen lists it: seven months after the year, the last day of February of
		the second year after it with a Steuerberatung, or the earliest day of a Vorabanforderung of the year, moved off a
		Saturday, a Sunday or a holiday of the company; none without Annual Filing Settings or before their first
		year."""
		return annual_deadline(self.company, Kind.KOERPERSCHAFTSTEUERERKLAERUNG, cint(self.year))

	def correction_values(self) -> dict[str, Any]:
		"""A Berichtigung starts with the statements and the tables of this return."""
		return {
			**{fieldname: self.get(fieldname) for fieldname in INPUT_FIELDS},
			**{table: [_input_row(row) for row in self.get(table) or ()] for table in INPUT_TABLES},
		}

	# Transmittable.

	def datenart(self) -> eric_datenart.Datenart:
		"""The Datenart KSt of the year of the return."""
		return eric_datenart.kst(cint(self.year))

	def nutzdaten(self, hersteller_id: str) -> str:
		"""The Nutzdaten E30 of the return as saved, with the Vorsatz; the Erklärung carries no Hersteller-ID of its
		own."""
		year = self._year()
		with core_errors(), xml_errors(_("ELSTER Transmission")):
			return kst_xml.to_nutzdaten(year, self.filed_vordrucke(), self.vorsatz())

	# Frappe.

	def before_insert(self) -> None:
		super().before_insert()
		self.provisions_entry = None

	def validate(self) -> None:
		before = self.get_doc_before_save()
		if not (self.company and self.year):
			super().validate()
			return
		self._catalogue()
		self._name_the_lines_by_hand(before)
		self._name_the_electronic_balance_sheet()
		super().validate()
		self.provisional = int(bridge.provisional(cint(self.year))[0])
		self.vorgang = VORGANG
		self.provisions_entry = before.provisions_entry if before is not None else None
		with core_errors():
			bridge.check_lines(cint(self.year), [row.as_dict() for row in self.lines])
			bridge.check_tables(self._return(), _)
			self._describe_the_lines_by_hand()
		self._fill_the_holding_results()
		self._require_berechnen_after_a_change(before)

	# Rückstellungen vorschlagen.

	@frappe.whitelist(methods=["POST"])
	@guards.on_stored("write")
	def propose_provisions(self) -> str:
		"""Rückstellungen vorschlagen: a draft Journal Entry of the balances of Körperschaftsteuer, Solidaritätszuschlag
		and Gewerbesteuer at the end of the Wirtschaftsjahr, on the accounts of the chart (steuerbote.kst.provisions).
		Returns the name of the Journal Entry, or nothing where no tax has a balance."""
		self.check_permission("write")
		frappe.has_permission(JOURNAL_ENTRY, "create", throw=True)
		if self.docstatus == 2 or self.status not in (*self.LIFECYCLE.calculated, *self.LIFECYCLE.filings):
			frappe.throw(_("Calculate {0} before proposing its provisions.").format(self.name))
		if self.provisions_entry and frappe.db.exists(
			JOURNAL_ENTRY, {"name": self.provisions_entry, "docstatus": 0}
		):
			frappe.throw(
				_(
					"The draft Journal Entry {0} holds the provisions proposed before. Check and submit it, or delete it to propose them again."
				).format(self.provisions_entry)
			)
		mapping = income_tax_sources.mapping(self.company)
		accounts = provisions.ACCOUNTS.get(mapping.chart)
		if accounts is None:
			frappe.throw(
				_(
					"Steuerbote knows the accounts of the provisions of SKR03 and SKR04, not those of a chart of its own."
				)
			)
		from_date, to_date = getdate(self.from_date), getdate(self.to_date)
		posted = self.posted_provisions() or {}
		ledger, settings = self.sources(mapping)
		computation = self.computation(mapping, ledger, settings)
		trade_tax = trade_tax_bridge.compute(
			trade_tax_bridge.Return(cint(self.year), from_date, to_date),
			computation,
			ledger,
			settings,
			self.figures(),
			_,
		).result
		if trade_tax.hebesatz is None:
			trade_tax = None
			frappe.msgprint(
				_(
					"The Annual Filing Settings give no Hebesatz for {0}, so the proposal leaves out the Gewerbesteuer."
				).format(self.year)
			)
		rows = provisions.propose(computation.result, trade_tax, accounts, posted)
		if not rows:
			if any(posted.values()):
				frappe.msgprint(
					_(
						"The books hold the provisions for the taxes of {0} as this return computes them."
					).format(self.year)
				)
			else:
				frappe.msgprint(_("No tax of {0} has a balance to provide for.").format(self.year))
			return ""
		entry = provision_entry(self.company, to_date, rows, self.name)
		self.db_set("provisions_entry", entry)
		return entry

	# What the print format, the Trade Tax Return and the report read.

	def income_tax_print(self) -> dict[str, Any]:
		"""The Vordrucke the return files, in the order and with the lines and Beschreibungen of the forms, for the print
		format „Körperschaftsteuererklärung“ (layout.print_sections)."""
		year = self._year()
		provisional, documentation_year = bridge.provisional(year)
		sections = layout.print_sections(
			catalogue_for(year), self.filed_vordrucke(), kst_xml.schema_for(year).repeats, bridge.IDENTIFIERS
		)
		return {"sections": sections, "provisional": provisional, "documentation_year": documentation_year}

	def filed_vordrucke(self):
		"""The Vordrucke the return files as saved."""
		rows = [row.as_dict() for row in self.lines]
		with core_errors():
			return bridge.filed_vordrucke(self._return(), rows, self.settings())

	def computation(
		self,
		mapping: Mapping | None = None,
		ledger: bridge.Ledger | None = None,
		settings: bridge.Settings | None = None,
	) -> bridge.Computation:
		"""The Körperschaftsteuer of the return as stored, on the ledger of today."""
		self._year()
		mapping = mapping or income_tax_sources.mapping(self.company)
		if ledger is None:
			ledger, settings = self.sources(mapping)
		with core_errors():
			return bridge.compute(self._return(), ledger, mapping, settings, self.figures(), _)

	def sources(self, mapping: Mapping) -> tuple[bridge.Ledger, bridge.Settings | None]:
		"""The ledger of the Wirtschaftsjahr and the Annual Filing Settings, as Berechnen reads them."""
		ledger = income_tax_sources.ledger(
			self.company,
			getdate(self.from_date),
			getdate(self.to_date),
			provisions.ACCOUNTS.get(mapping.chart),
			income_tax_sources.commercial_finance_book(self.company),
		)
		return ledger, self.settings()

	def settings(self) -> bridge.Settings | None:
		return income_tax_sources.settings(self.company, cint(self.year))

	def figures(self) -> SiteFigures:
		return SiteFigures(frappe.get_cached_value("Company", self.company, "default_currency"))

	# The rules of a save.

	def _name_the_lines_by_hand(self, before: Document | None) -> None:
		"""A line by hand names its field by its Feldkennung, as the catalogue writes it."""
		stored = {row.name: cint(row.manual) for row in (before.get(self.LINES) if before else ())}
		for row in self.lines:
			if stored.get(row.name, 1):
				row.feldkennung = bridge.normalized(row.feldkennung)

	def _name_the_electronic_balance_sheet(self) -> None:
		"""A new return names the E-Bilanz of its company and year that Berechnen would take; a return names no E-Bilanz
		of another company, year or Bilanzart, and no cancelled one."""
		if self.is_new() and not self.electronic_balance_sheet:
			self.electronic_balance_sheet = ebilanz_sources.ebilanz_for_income_tax(
				self.company, cint(self.year), None
			)
		if not self.electronic_balance_sheet:
			return
		named = frappe.db.get_value(
			ebilanz_sources.DOCTYPE,
			self.electronic_balance_sheet,
			["name", "company", "year", "statement_type", "docstatus"],
			as_dict=True,
		)
		if named is None or cint(named.docstatus) == 2:
			frappe.throw(
				_("{0} is no E-Bilanz that is not cancelled.").format(
					frappe.bold(self.electronic_balance_sheet)
				)
			)
		if (named.company, cint(named.year), named.statement_type) != (
			self.company,
			cint(self.year),
			ebilanz_sources.JAHRESABSCHLUSS,
		):
			frappe.throw(
				_(
					"The E-Bilanz {0}, {1}, is one of {2} for {3}; the Körperschaftsteuererklärung of {4} for {5} takes the E-Bilanz of the Jahresabschluss of its own company and year."
				).format(named.name, named.statement_type, named.company, named.year, self.company, self.year)
			)

	def _describe_the_lines_by_hand(self) -> None:
		"""A line by hand takes the form, line and Beschreibung of its field, which has to take one."""
		for row in self.lines:
			if cint(row.manual):
				row.update(bridge.describe(bridge.manual_field(cint(self.year), row.feldkennung)))

	def _fill_the_holding_results(self) -> None:
		"""The § 8b results of dividends show the shares of the holdings register and what § 8b KStG makes of them, and
		a sale its result, the price less the costs and the book value."""
		settings = self.settings()
		for row in self.holding_results:
			registered, exemption = bridge.holding_exemption(cint(self.year), row.as_dict(), settings)
			row.update(
				{
					"percent_on_1_january": flt(registered.percent_on_1_january) if registered else 0,
					"percent_at_start_of_ez": flt(registered.percent_at_start_of_ez) if registered else 0,
					"exemption": exemption,
				}
			)
			if row.kind == bridge.SALE:
				row.amount = flt(bridge.sale_result(row.as_dict()))

	def _require_berechnen_after_a_change(self, before: Document | None) -> None:
		"""A calculated return whose tables or statements changed is Berechnet again, with a finding that asks for
		Berechnen."""
		if before is None or self.flags.calculating or self.status not in self.LIFECYCLE.calculated:
			return
		if inputs(before) == inputs(self):
			return
		self.status = self.LIFECYCLE.move(self.status, Event.CHANGE)
		self.ready = 0
		stored = annual_findings.of_rows([row.as_dict() for row in self.get(FINDINGS_TABLE) or ()])
		if any(finding.code == RECALCULATE for finding in stored):
			return
		recalculate = Finding(
			RECALCULATE,
			Severity.ERROR,
			_(
				"An entry that Berechnen reads changed since Berechnen: a table of the return or one of its statements. Calculate again, so that Berechnen checks the return with it."
			),
		)
		self.add_finding(recalculate)

	# Helpers.

	def _year(self) -> int:
		self._catalogue()
		return cint(self.year)

	def _catalogue(self) -> None:
		"""The Vordrucke of the Körperschaftsteuer of the year of the return, with the schema of their XML."""
		try:
			catalogue_for(cint(self.year))
			kst_xml.schema_for(cint(self.year))
		except UnknownYearError:
			frappe.throw(
				_("Steuerbote has no forms of the Körperschaftsteuer for {0} yet.").format(cint(self.year))
			)

	def _return(self, lines=None) -> bridge.Return:
		"""The return as the bridge reads it, with the lines given or those of the return."""
		return bridge.Return(
			cint(self.year),
			getdate(self.from_date),
			getdate(self.to_date),
			lines=tuple(lines if lines is not None else (row.as_dict() for row in self.lines)),
			**{table: tuple(row.as_dict() for row in self.get(table) or ()) for table in INPUT_TABLES},
			supplement_key=self.supplement_key or None,
			supplement_text=self.supplement_text or None,
			shareholder_contracts=bool(cint(self.shareholder_contracts)),
			carry_back_chosen=bool(cint(self.carry_back_chosen)),
			loss_carry_back=self.loss_carry_back,
			turnover_and_wages_given=bool(cint(self.turnover_and_wages_given)),
			turnover_and_wages=self.turnover_and_wages,
			previous_equity=self.previous_equity,
			previous_nominal_capital=self.previous_nominal_capital,
			ebilanz=income_tax_sources.ebilanz(self.electronic_balance_sheet, self.company),
			prior_ebilanz=income_tax_sources.prior_ebilanz(self.company, cint(self.year)),
			first_year=income_tax_sources.first_year(self.company, DOCTYPE, cint(self.year)),
		)


@contextmanager
def core_errors() -> Iterator[None]:
	"""Show what the bridge refuses as a message in the language of the user."""
	try:
		yield
	except bridge.BridgeError as error:
		frappe.throw(_(error.template).format(*error.values), title=_(DOCTYPE))


def provision_entry(company: str, posting_date: date, rows, document: str) -> str:
	"""The draft Journal Entry of the provisions, on the last day of the Wirtschaftsjahr: a debit and a credit of each
	row of steuerbote.kst.provisions, each with its remark. Returns its name."""
	numbers = sorted({number for row in rows for number in (row.debit_account, row.credit_account)})
	names = account_names(company, numbers)
	missing = [number for number in numbers if number not in names]
	if missing:
		frappe.throw(
			_(
				"{0} lacks the accounts {1} of the provisions. Create them before proposing the provisions."
			).format(company, ", ".join(missing))
		)
	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	accounts = []
	for row in rows:
		for account, side in ((row.debit_account, "debit"), (row.credit_account, "credit")):
			accounts.append(
				{
					"account": names[account],
					f"{side}_in_account_currency": row.amount,
					"cost_center": cost_center,
					"user_remark": row.remark,
				}
			)
	entry = frappe.get_doc(
		{
			"doctype": JOURNAL_ENTRY,
			"voucher_type": JOURNAL_ENTRY,
			"company": company,
			"posting_date": posting_date,
			"user_remark": _("Provisions for the taxes on income proposed by {0}").format(document),
			"accounts": accounts,
		}
	)
	entry.insert()
	return entry.name


def inputs(doc: Document) -> tuple:
	"""What Berechnen reads of a return besides its lines, comparable between two states of it."""
	values = tuple(
		_value(doc.meta.get_field(fieldname).fieldtype, doc.get(fieldname)) for fieldname in INPUT_FIELDS
	)
	tables = []
	for table in INPUT_TABLES:
		meta = frappe.get_meta(doc.meta.get_field(table).options)
		tables.append(
			tuple(
				tuple(
					(key, _value(meta.get_field(key).fieldtype, value))
					for key, value in sorted(_input_row(row).items())
					if meta.get_field(key) is not None
				)
				for row in doc.get(table) or ()
			)
		)
	return values, tuple(tables)


def _input_row(row: Document) -> dict[str, Any]:
	"""A row of an input table as a Berichtigung takes it, without what Frappe or a save fills in."""
	values = row.as_dict(no_default_fields=True, no_child_table_fields=True)
	return {key: value for key, value in values.items() if key not in HOLDING_COLUMNS}


def _value(fieldtype: str, value: object) -> str:
	if fieldtype in ("Check", "Int"):
		return str(cint(value))
	if fieldtype in ("Currency", "Float", "Percent"):
		return format(flt(value, 2), ".2f")
	if fieldtype == "Date":
		return getdate(value).isoformat() if value else ""
	return " ".join(str(value or "").split())
