"""Trade Tax Return: the Gewerbesteuererklärung of a GmbH or UG for one Erhebungszeitraum (GewSt 1 A and Anlagen BEG;
§ 14a GewStG).

The document lives on the base of the annual documents (steuerbote/steuerbote/annual_filing.py, docs/jahresmeldungen.md),
as the Körperschaftsteuererklärung does, and builds on the Corporate Income Tax Return of its company and year, which
it names (corporate_income_tax_return): there is one computation, and the Gewinn of line 39 follows from the Summe
der Einkünfte of the Körperschaftsteuer.

- Berechnen (compute) runs the Körperschaftsteuer of that return as it is stored, on the ledger of today, and the core
  in steuerbote/gewst on it, through bridge.py, with the Hebesatz of the one Gemeinde, the carry-forwards and the
  Vorauszahlungen of the Annual Filing Settings; on the lines as filed it checks the rules of the Jahresdokumentation
  E20 that Steuerbote checks itself (check_reported).
- A save names the Körperschaftsteuererklärung of the company and year where the return names none, refuses one of
  another company or year, and refuses corrections and lines by hand: they belong to the Körperschaftsteuererklärung
  and the Income Tax Mapping, which the lines come from.
- The deadline is the day Offene Fristen lists for the Gewerbesteuererklärung of the year (annual_deadline): § 149
  Absatz 2 to 4 AO with the Steuerberatung and the Vorabanforderung of the Annual Filing Settings.
- Prüfen, Testsenden and Senden go through ERiC in the Datenart GewSt of the year (datenart.gewst) with the Nutzdaten
  E20 of steuerbote/elster/gewst_xml.py; Mein ELSTER imports no Gewerbesteuererklärung, it is typed in there from the
  print format „Gewerbesteuererklärung“.
"""

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from steuerbote import income_tax_sources
from steuerbote.deadlines import Kind
from steuerbote.elster import gewst_xml
from steuerbote.eric import datenart as eric_datenart
from steuerbote.gewst.form import catalogue_for
from steuerbote.jahresmeldung import findings as annual_findings
from steuerbote.jahresmeldung.findings import Finding, Severity
from steuerbote.jahresmeldung.lifecycle import Event
from steuerbote.jahresmeldung.overrides import correction_of
from steuerbote.steuerbote.annual_filing import FINDINGS_TABLE, RECALCULATE, AnnualFiling, Calculation
from steuerbote.steuerbote.deadlines import annual_deadline
from steuerbote.steuerbote.doctype.corporate_income_tax_return import layout
from steuerbote.steuerbote.doctype.corporate_income_tax_return.corporate_income_tax_return import (
	DOCTYPE as CORPORATE_INCOME_TAX_RETURN,
)
from steuerbote.steuerbote.doctype.elster_transmission.transmission import Transmittable
from steuerbote.steuerbote.doctype.trade_tax_return import bridge
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors
from steuerbote.ustva.years import UnknownYearError

DOCTYPE = "Trade Tax Return"
VORGANG = "01"
INPUT_FIELDS = ("corporate_income_tax_return", "supplement_key", "supplement_text")
"""What Berechnen reads of the return beside the Körperschaftsteuererklärung it names."""
REPLACED = "Ersetzt"


class TradeTaxReturn(AnnualFiling, Transmittable, Document):
	LINES = "lines"
	LINE_COLUMNS = bridge.LINE_COLUMNS
	CALCULATED_TABLES = ("municipalities", "holdings", "donations")
	CALCULATED_FIELDS = (
		"profit",
		"financing_addback",
		"gewerbeertrag",
		"messbetrag",
		"hebesatz",
		"gewst",
		"prepayments",
		"balance",
	)

	# The hooks of the base.

	def compute(self) -> Calculation:
		"""Berechnen: the Gewerbesteuer of the year on the Körperschaftsteuer of the return it names."""
		corporate = self._corporate_income_tax_return()
		mapping = income_tax_sources.mapping(corporate.company)
		ledger, settings = corporate.sources(mapping)
		computation = corporate.computation(mapping, ledger, settings)
		trade_tax = bridge.compute(self._return(), computation, ledger, settings, corporate.figures(), _)
		return Calculation(
			lines=trade_tax.lines,
			tables={
				"municipalities": trade_tax.municipalities,
				"holdings": trade_tax.holdings,
				"donations": [_receipt(row) for row in corporate.donations],
			},
			values=trade_tax.values,
			findings=trade_tax.findings,
		)

	def check_reported(self, lines) -> list[Finding]:
		"""The rules of the Jahresdokumentation E20 that Steuerbote checks itself, on the Vordrucke the return files."""
		year = self._year()
		filed = bridge.filed_vordrucke(
			self._return(),
			lines,
			[row.as_dict() for row in self.holdings],
			[row.as_dict() for row in self.municipalities],
			[row.as_dict() for row in self.donations],
			self._settings(),
		)
		return bridge.rule_findings(year, filed, _)

	def compute_deadline(self) -> date | None:
		"""The day the return is due, as Offene Fristen lists it (§ 149 Absatz 2 to 4 AO, § 108 Absatz 3 AO)."""
		return annual_deadline(self.company, Kind.GEWERBESTEUERERKLAERUNG, cint(self.year))

	def correction_values(self) -> dict[str, Any]:
		"""A Berichtigung starts with the qualified free text and names the Körperschaftsteuererklärung of the year that
		is filed latest, or the draft of one."""
		return {
			"supplement_key": self.supplement_key,
			"supplement_text": self.supplement_text,
			"corporate_income_tax_return": latest_corporate_income_tax_return(self.company, cint(self.year)),
		}

	# Transmittable.

	def datenart(self) -> eric_datenart.Datenart:
		"""The Datenart GewSt of the year of the return."""
		return eric_datenart.gewst(cint(self.year))

	def nutzdaten(self, hersteller_id: str) -> str:
		"""The Nutzdaten E20 of the return as saved, with the Vorsatz."""
		year = self._year()
		with xml_errors(_("ELSTER Transmission")):
			return gewst_xml.to_nutzdaten(year, self.filed_vordrucke(), self.vorsatz())

	# Frappe.

	def validate(self) -> None:
		before = self.get_doc_before_save()
		if self.company and self.year:
			self._catalogue()
			if not self.corporate_income_tax_return:
				self.corporate_income_tax_return = latest_corporate_income_tax_return(
					self.company, cint(self.year)
				)
			self._check_the_corporate_income_tax_return()
		super().validate()
		if not (self.company and self.year):
			return
		self.provisional = int(bridge.provisional(cint(self.year))[0])
		self.vorgang = VORGANG
		self._refuse_corrections()
		self._require_berechnen_after_a_change(before)

	# What the print format reads.

	def income_tax_print(self) -> dict[str, Any]:
		"""GewSt 1 A and the Anlagen BEG the return files, in the order and with the lines and Beschreibungen of the
		forms, for the print format „Gewerbesteuererklärung“ (layout.print_sections)."""
		year = self._year()
		provisional, documentation_year = bridge.provisional(year)
		sections = layout.print_sections(
			catalogue_for(year), self.filed_vordrucke(), gewst_xml.schema_for(year).repeats
		)
		return {"sections": sections, "provisional": provisional, "documentation_year": documentation_year}

	def filed_vordrucke(self):
		"""GewSt 1 A and the Anlagen BEG the return files as saved."""
		return bridge.filed_vordrucke(
			self._return(),
			[row.as_dict() for row in self.lines],
			[row.as_dict() for row in self.holdings],
			[row.as_dict() for row in self.municipalities],
			[row.as_dict() for row in self.donations],
			self._settings(),
		)

	# The rules of a save.

	def _check_the_corporate_income_tax_return(self) -> None:
		"""The return names a Körperschaftsteuererklärung of its company and year that is not cancelled."""
		if not self.corporate_income_tax_return:
			return
		named = frappe.db.get_value(
			CORPORATE_INCOME_TAX_RETURN,
			self.corporate_income_tax_return,
			["name", "company", "year", "docstatus"],
			as_dict=True,
		)
		if named is None or cint(named.docstatus) == 2:
			frappe.throw(
				_("{0} is no Körperschaftsteuererklärung that is not cancelled.").format(
					frappe.bold(self.corporate_income_tax_return)
				)
			)
		if (named.company, cint(named.year)) != (self.company, cint(self.year)):
			frappe.throw(
				_(bridge.OTHER_KEY).format(named.name, named.company, named.year, self.company, self.year)
			)

	def _refuse_corrections(self) -> None:
		for row in self.lines:
			if cint(row.manual) or correction_of(row.as_dict(), self.LINE_COLUMNS) is not None:
				frappe.throw(_(bridge.NOT_CORRECTED), title=_(DOCTYPE))

	def _require_berechnen_after_a_change(self, before: Document | None) -> None:
		"""A calculated return whose Körperschaftsteuererklärung or free text changed is Berechnet again, with a finding
		that asks for Berechnen."""
		if before is None or self.flags.calculating or self.status not in self.LIFECYCLE.calculated:
			return
		if all((before.get(name) or "") == (self.get(name) or "") for name in INPUT_FIELDS):
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
				"An entry that Berechnen reads changed since Berechnen: the Körperschaftsteuererklärung or the supplementary information. Calculate again, so that Berechnen checks the return with it."
			),
		)
		self.set(FINDINGS_TABLE, annual_findings.rows((*stored, recalculate)))

	# Helpers.

	def _corporate_income_tax_return(self):
		if not self.corporate_income_tax_return:
			frappe.throw(
				_(bridge.NO_CORPORATE_INCOME_TAX_RETURN).format(self.company, self.year), title=_(DOCTYPE)
			)
		return frappe.get_doc(CORPORATE_INCOME_TAX_RETURN, self.corporate_income_tax_return)

	def _year(self) -> int:
		self._catalogue()
		return cint(self.year)

	def _catalogue(self) -> None:
		"""The Vordrucke of the Gewerbesteuer of the year of the return, with the schema of their XML."""
		try:
			catalogue_for(cint(self.year))
			gewst_xml.schema_for(cint(self.year))
		except UnknownYearError:
			frappe.throw(
				_("Steuerbote has no forms of the Gewerbesteuer for {0} yet.").format(cint(self.year))
			)

	def _settings(self):
		return income_tax_sources.settings(self.company, cint(self.year))

	def _return(self) -> bridge.Return:
		return bridge.Return(
			cint(self.year),
			getdate(self.from_date),
			getdate(self.to_date),
			supplement_key=self.supplement_key or None,
			supplement_text=self.supplement_text or None,
			first_year=income_tax_sources.first_year(self.company, DOCTYPE, cint(self.year)),
		)


def latest_corporate_income_tax_return(company: str, year: int) -> str | None:
	"""The Körperschaftsteuererklärung of the company and year that the Gewerbesteuererklärung builds on: the draft of
	one, else the one filed latest that no Berichtigung replaced."""
	found = frappe.get_all(
		CORPORATE_INCOME_TAX_RETURN,
		filters={"company": company, "year": year, "docstatus": ["!=", 2], "status": ["!=", REPLACED]},
		fields=["name", "docstatus"],
		order_by="creation desc",
	)
	drafts = [row.name for row in found if cint(row.docstatus) == 0]
	return (drafts or [row.name for row in found] or [None])[0]


def _receipt(row: Document) -> dict[str, Any]:
	"""A Zuwendungsbestätigung of the Körperschaftsteuererklärung as GewSt 1 A lines 92a to 92c take it."""
	return {"recipient": row.recipient, "amount": row.amount, "abroad": cint(row.abroad)}
