"""Electronic Balance Sheet: the E-Bilanz of one company for one Wirtschaftsjahr and Bilanzart (§ 5b EStG).

The document lives on the base of the annual documents (steuerbote/steuerbote/annual_filing.py, docs/jahresmeldungen.md):
its status, Berechnen with the corrections and lines by hand, the findings, the filing, the Berichtigung by the Status
des Berichts and the transmission through ERiC are those of AnnualFiling and Transmittable. Its key is the company, the
year the Wirtschaftsjahr ends in and the Bilanzart, Jahresabschluss or the Eröffnungsbilanz of the founding year
(§ 5b Abs. 1 Satz 4 EStG). This controller gives it the E-Bilanz:

- Berechnen (compute) builds the case of the document (bridge.case_of) and its structure on the fiscal view of the
  installed HGB-Taxonomie (steuerbote/ebilanz/positions.py), reads the books through steuerbote/ebilanz_sources.py
  and places them with the Balance Sheet Mapping of the company, takes the Anlagenspiegel from the report Asset
  Depreciations and Balances with the columns by hand of the document, the Überleitung of a Handelsbilanz from the
  finance book of the Steuerbilanz or by hand, the Betriebsvermögensvergleich and the GCD, and builds the E-Bilanz
  (steuerbote.ebilanz.instance.build). bridge.py moves the results into the tables and fields of the document.
- „Bereit“ follows from the findings: the taxonomy is installed and unchanged, the Bilanzzuordnung names its version,
  no balance is without its place and no check of the E-Bilanz finds an error, every adjustment of ERPNext on a fixed
  asset account is in a column of the Anlagenspiegel, the depreciation is posted up to the Bilanzstichtag and the GCD
  is complete. A missing Period Closing Voucher is a hint only, since the balances neither need it nor count the
  result twice. A Bilanzzuordnung on another version (SB-ZUORDNUNG-VERSION) has its books placed on the positions of
  the taxonomy of the E-Bilanz, as far as that version has them, so that Berechnen shows the other findings as well.
- Berechnen compares the Handelsbilanz with that of the Jahresabschluss of the company and year (comparison.py), which
  the E-Bilanz names (annual_accounts): a festgestellter Jahresabschluss that differs holds it back from „Bereit“, one
  that is not festgestellt yet gives a hint. A new E-Bilanz names it, and it is filed only while it names none that
  was cancelled since Berechnen, as before an amendment of the Jahresabschluss.
- A save takes the corrections and lines by hand of the positions, the columns by hand of the Anlagenspiegel, the
  entries by hand of the Überleitung and what the Betriebsvermögensvergleich takes beyond the books; a change of what
  Berechnen reads leaves a calculated E-Bilanz Berechnet until Berechnen checks it again, and it is filed only after.
- The Nutzdaten, the XBRL file and the checks before them take the E-Bilanz as the document holds it
  (bridge.sources_of), and refuse it where it no longer gives the amounts stored, as after a change of the taxonomy.
- Prüfen, Testsenden and Senden go through ERiC in the Datenart Bilanz of the taxonomy (datenart.bilanz), Prüfen with
  EBV-8, in the simulation, which checks the Mussfelder and the sums with the installed taxonomy, until the
  Hersteller-ID exists. Mein ELSTER takes no E-Bilanz: without the Hersteller-ID the way is „XBRL exportieren“ for the
  Steuerberatung and „Als außerhalb abgegeben vermerken“.
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.core.doctype.file.utils import get_content_hash
from frappe.model.document import Document
from frappe.utils import cint, escape_html, getdate

from steuerbote import balances, ebilanz_sources
from steuerbote.balance_mapping_sync import davon_values, ebilanz_balances, ebilanz_davon_lines
from steuerbote.dauerfrist_sources import date_of_establishment
from steuerbote.deadlines import Kind
from steuerbote.ebilanz import instance, positions
from steuerbote.ebilanz.calculation import EquityChanges, calculate
from steuerbote.ebilanz.instance import EBilanz, Sources
from steuerbote.ebilanz.positions import AccountingStandard, CaseError, Structure
from steuerbote.ebilanz.ueberleitung import ueberleitung
from steuerbote.elster import ebilanz_xml
from steuerbote.eric import datenart as eric_datenart
from steuerbote.eric.simulation import bilanz as simulated_bilanz
from steuerbote.jahresmeldung import findings as annual_findings
from steuerbote.jahresmeldung.findings import Finding, Severity
from steuerbote.jahresmeldung.lifecycle import Event
from steuerbote.jahresmeldung.overrides import OverrideError, to_amount
from steuerbote.steuerbote.annual_filing import FINDINGS_TABLE, RECALCULATE, AnnualFiling, Calculation
from steuerbote.steuerbote.deadlines import annual_deadline
from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import settings_of
from steuerbote.steuerbote.doctype.balance_sheet_mapping.balance_sheet_mapping import position_taxonomy
from steuerbote.steuerbote.doctype.electronic_balance_sheet import bridge, comparison, layout
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import OTHER_WAY
from steuerbote.steuerbote.doctype.elster_transmission.transmission import Transmittable
from steuerbote.steuerbote.doctype.eric_settings import eric_settings
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors
from steuerbote.xbrl.mapping import Books, Placement, Purpose, part_of, place, position_of
from steuerbote.xbrl.taxonomy import Taxonomy, View

DOCTYPE = "Electronic Balance Sheet"
MAPPING = "Balance Sheet Mapping"
FIXED_ASSETS = "fixed_assets"
TRANSFERS = "transfers"
ACCOUNTS = "accounts"
COMPONENTS = {"Bilanz": "B", "GuV": "GuV"}


class ElectronicBalanceSheet(AnnualFiling, Transmittable, Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.annual_filing_finding.annual_filing_finding import (
			AnnualFilingFinding,
		)
		from steuerbote.steuerbote.doctype.electronic_balance_sheet_account.electronic_balance_sheet_account import (
			ElectronicBalanceSheetAccount,
		)
		from steuerbote.steuerbote.doctype.electronic_balance_sheet_fixed_asset.electronic_balance_sheet_fixed_asset import (
			ElectronicBalanceSheetFixedAsset,
		)
		from steuerbote.steuerbote.doctype.electronic_balance_sheet_position.electronic_balance_sheet_position import (
			ElectronicBalanceSheetPosition,
		)
		from steuerbote.steuerbote.doctype.electronic_balance_sheet_transfer.electronic_balance_sheet_transfer import (
			ElectronicBalanceSheetTransfer,
		)

		accounting_standard: DF.Literal["HAOE", "HGBM", "AO"]
		accounts: DF.Table[ElectronicBalanceSheetAccount]
		amended_from: DF.Link | None
		annual_accounts: DF.Link | None
		bvv_capital_adjustments: DF.Currency
		bvv_contributions: DF.Currency
		bvv_founding_contribution: DF.Currency
		bvv_previous_equity: DF.Currency
		bvv_previous_equity_override: DF.Currency
		bvv_previous_equity_reason: DF.SmallText | None
		bvv_withdrawals: DF.Currency
		commercial_finance_book: DF.Link | None
		company: DF.Link
		corrects: DF.Link | None
		deadline: DF.Date | None
		filed_by: DF.Link | None
		filed_on: DF.Date | None
		filed_via: DF.Literal["", "eric", "mein_elster", "other_way", "upload"]
		filing_note: DF.SmallText | None
		findings: DF.Table[AnnualFilingFinding]
		first_fiscal_year: DF.Check
		fiscal_year: DF.Link | None
		fixed_assets: DF.Table[ElectronicBalanceSheetFixedAsset]
		from_date: DF.Date | None
		is_correction: DF.Check
		naming_series: DF.Literal["EB-.{year}.-.#####"]
		net_income: DF.Currency
		positions: DF.Table[ElectronicBalanceSheetPosition]
		ready: DF.Check
		remarks: DF.SmallText | None
		revision_status: DF.Literal["", "E", "B", "G", "BG", "sK", "I"]
		statement_type: DF.Literal["Jahresabschluss", "Eröffnungsbilanz"]
		status: DF.Literal["Entwurf", "Berechnet", "Bereit", "Abgegeben", "Ersetzt"]
		stichtag: DF.Date | None
		tax_equity: DF.Currency
		tax_finance_book: DF.Link | None
		tax_net_income: DF.Currency
		taxonomy_version: DF.Literal["6.9", "6.10"]
		to_date: DF.Date | None
		total_assets: DF.Currency
		total_equity_and_liabilities: DF.Currency
		transfers: DF.Table[ElectronicBalanceSheetTransfer]
		transferticket: DF.Data | None
		transmission_in_progress: DF.Check
		year: DF.Int
	# end: auto-generated types

	KEY_FIELDS = ("company", "year", "statement_type")
	LINES = "positions"
	LINE_COLUMNS = bridge.LINE_COLUMNS
	CALCULATED_TABLES = (ACCOUNTS,)
	CALCULATED_FIELDS = (
		"first_fiscal_year",
		"annual_accounts",
		"total_assets",
		"total_equity_and_liabilities",
		"net_income",
		"tax_net_income",
		"tax_equity",
		"bvv_previous_equity",
		"bvv_founding_contribution",
	)
	FILED_OUTSIDE = (OTHER_WAY,)

	# The hooks of the base.

	def compute(self) -> Calculation:
		"""Berechnen: the E-Bilanz of the Wirtschaftsjahr from the books, the assets and the settings."""
		settings = self._settings()
		view = eric_settings.taxonomy_view(self.taxonomy_version, View.FISCAL)
		unchanged, detail = ebilanz_sources.taxonomy_check(self.taxonomy_version)
		structure = self._structure(settings, view)
		mapping = self._mapping()
		purpose = bridge.purpose_of(self.accounting_standard)
		book = self._book()
		placement, closed_by = self._placement(mapping, purpose, book)
		stored = self._rows(self.LINES)
		with core_errors():
			adjustments = (*ebilanz_davon_lines(placement, view), *bridge.adjustments_of(stored))
			assets = self._asset_rows(mapping, view)
			transfers = self._transfer_rows(mapping, structure, placement)
		balances_ = ebilanz_balances(placement)
		first_year = self._first_year()
		previous, founding = self._previous_equity(
			structure, mapping, purpose, book, first_year, balances_, adjustments, transfers
		)
		values = {"bvv_previous_equity": previous, "bvv_founding_contribution": founding}
		with core_errors():
			sources = Sources(
				balances=balances_,
				adjustments=adjustments,
				assets=bridge.assets_of(assets),
				transfers=bridge.transfers_of(transfers) if self._handelsbilanz else (),
				equity=self._equity_changes(previous, founding),
				first_year=first_year,
			)
		ebilanz = instance.build(structure, self._master(settings, first_year), sources)
		accounts = self._annual_accounts()
		found = (
			*bridge.taxonomy_finding(self.taxonomy_version, unchanged, detail),
			*bridge.mapping_version_finding(
				self.taxonomy_version,
				mapping.taxonomy_version,
				getdate(self.from_date),
				getdate(self.to_date),
			),
			*bridge.placement_findings(placement),
			*ebilanz.annual_findings(),
			*bridge.asset_findings(structure, assets),
			*bridge.depreciation_findings(
				ebilanz_sources.unposted_depreciation(
					self.company,
					getdate(self.stichtag),
					bridge.finance_books(
						self.accounting_standard, self.commercial_finance_book, self.tax_finance_book
					),
				),
				getdate(self.stichtag),
			),
			*bridge.schedule_findings(
				ebilanz_sources.schedules(self.company, getdate(self.from_date), getdate(self.stichtag)),
				bridge.finance_books(
					self.accounting_standard, self.commercial_finance_book, self.tax_finance_book
				),
			),
			*bridge.closing_finding(self.statement_type, closed_by),
			*self._comparison_findings(ebilanz, accounts),
		)
		return Calculation(
			lines=bridge.position_rows(
				ebilanz, davon_values(placement, view), bridge.corrected(stored), bridge.by_hand(stored)
			),
			tables={
				ACCOUNTS: bridge.account_rows(ebilanz, bridge.account_names(placement)),
				FIXED_ASSETS: bridge.fixed_asset_rows(structure, assets),
				TRANSFERS: bridge.labelled_transfers(structure, transfers),
			},
			values={
				**bridge.totals(ebilanz),
				**values,
				"first_fiscal_year": int(first_year),
				"annual_accounts": accounts,
			},
			findings=found,
			passed=ebilanz.report is not None,
		)

	def compute_deadline(self) -> date | None:
		"""The day the E-Bilanz is due, as Offene Fristen lists it: that of the Körperschaftsteuererklärung of the year
		the Wirtschaftsjahr ends in (FAQ zur E-Bilanz, Version 2026-01, Tz. 5), the Eröffnungsbilanz with it."""
		return annual_deadline(self.company, Kind.E_BILANZ, cint(self.year), opening_balance=self._opening)

	def check_filing(self) -> None:
		"""An E-Bilanz whose corrections or inputs changed since Berechnen is calculated again before it is filed: its
		sums, the Steuerbilanz and the Betriebsvermögensvergleich follow from them through the taxonomy. So is one whose
		Jahresabschluss was cancelled since Berechnen compared it, before Senden, since a filed E-Bilanz names no
		cancelled document."""
		if any(row.code == RECALCULATE for row in self.get(FINDINGS_TABLE) or ()):
			frappe.throw(
				_(
					"Something Berechnen reads changed since Berechnen. Calculate {0} again before filing it: its sums follow from the corrections through the HGB-Taxonomie."
				).format(self.name)
			)
		if self.annual_accounts and ebilanz_sources.cancelled_annual_accounts(self.annual_accounts):
			frappe.throw(
				_(
					"The Jahresabschluss {0} was cancelled since Berechnen compared {1} with it. Calculate {1} again, so that Berechnen compares it with the Jahresabschluss that amends it."
				).format(self.annual_accounts, self.name)
			)

	def correction_values(self) -> dict[str, Any]:
		"""A Berichtigung starts with the basis of this E-Bilanz, what the Betriebsvermögensvergleich takes beyond the
		books, the columns by hand of the Anlagenspiegel and the entries by hand of the Überleitung; it names its own
		Status des Berichts."""
		return {
			**{fieldname: self.get(fieldname) for fieldname in bridge.INPUT_FIELDS},
			FIXED_ASSETS: bridge.asset_inputs(self._rows(FIXED_ASSETS)),
			TRANSFERS: bridge.transfer_inputs(self._rows(TRANSFERS)),
		}

	def set_period(self) -> None:
		"""The period of the base, whose Fiscal Year of the company comes before one for every company, so that a short
		first Wirtschaftsjahr has its E-Bilanz on a site with a calendar year for all; the Bilanzstichtag, the end of
		the Wirtschaftsjahr, or its first day for an Eröffnungsbilanz; and the version of the HGB-Taxonomie of the
		Wirtschaftsjahr (bridge.taxonomy_for)."""
		super().set_period()
		start, end = getdate(self.from_date), getdate(self.to_date)
		self.stichtag = start if self._opening else end
		self.taxonomy_version = bridge.taxonomy_for(start, end, self.taxonomy_version)

	# Transmittable.

	def datenart(self) -> eric_datenart.Datenart:
		"""The Datenart Bilanz of the taxonomy of the E-Bilanz, such as Bilanz_6.9."""
		return eric_datenart.bilanz(self.taxonomy_version)

	def nutzdaten(self, hersteller_id: str) -> str:
		"""The Nutzdaten of the E-Bilanz as saved; the simulation checks them against the installed taxonomy."""
		version = self.taxonomy_version
		simulated_bilanz.register_taxonomy(version, lambda: eric_settings.taxonomy_view(version, View.FISCAL))
		ebilanz = self.stored_ebilanz()
		with xml_errors(_("ELSTER Transmission")):
			return ebilanz_xml.to_nutzdaten(ebilanz)

	# Frappe.

	def onload(self) -> None:
		super().onload()
		self.set_onload("electronic_balance_sheet", self._form_state())

	def before_insert(self) -> None:
		"""A new E-Bilanz keeps of its Anlagenspiegel the columns by hand and the rows by hand, and of its Überleitung the
		entries by hand; Berechnen fills the rest."""
		assets = bridge.asset_inputs(self._rows(FIXED_ASSETS))
		transfers = bridge.transfer_inputs(self._rows(TRANSFERS))
		super().before_insert()
		self.set(FIXED_ASSETS, assets)
		self.set(TRANSFERS, transfers)

	def validate(self) -> None:
		before = self.get_doc_before_save()
		if not all(self.get(fieldname) for fieldname in self.KEY_FIELDS):
			super().validate()
			return
		self._take_the_finance_books()
		self._keep_the_inputs(before)
		super().validate()
		self._name_the_annual_accounts()
		self._take_the_lines_by_hand()
		self._require_berechnen_after_a_change(before)

	# What the form and the print format read.

	@frappe.whitelist(methods=["POST"])
	def export_xbrl(self) -> str:
		"""XBRL exportieren: the instance of the E-Bilanz as saved, for the Steuerberatung, attached privately. A filed
		E-Bilanz gives the file as it was filed, a draft one while it could be filed. Returns the address of the
		file."""
		self.check_permission("write")
		saved = frappe.get_doc(self.doctype, self.name)
		saved.require_fit_for_export()
		ebilanz = saved.stored_ebilanz()
		return saved._attach(saved._file_name(), ebilanz.xml())

	def stored_ebilanz(self) -> EBilanz:
		"""The E-Bilanz as the document holds it, for the Nutzdaten and the XBRL file; refused where it no longer gives
		the amounts the positions store or has no instance."""
		settings = self._settings()
		view = eric_settings.taxonomy_view(self.taxonomy_version, View.FISCAL)
		structure = self._structure(settings, view)
		with core_errors():
			sources = bridge.sources_of(
				structure,
				positions=self._rows(self.LINES),
				accounts=self._rows(ACCOUNTS),
				fixed_assets=self._rows(FIXED_ASSETS),
				transfers=self._rows(TRANSFERS) if self._handelsbilanz else (),
				equity=self._equity_changes(
					to_amount(self.bvv_previous_equity), to_amount(self.bvv_founding_contribution)
				),
				first_year=bool(cint(self.first_fiscal_year)),
			)
		ebilanz = instance.build(
			structure, self._master(settings, bool(cint(self.first_fiscal_year))), sources
		)
		differences = bridge.differences(ebilanz, self._rows(self.LINES))
		if differences:
			concept, stored, given = differences[0]
			frappe.throw(
				_(
					"The position {0} reports {1} as stored, the E-Bilanz of the document gives {2}: calculate it again."
				).format(escape_html(concept), stored, given)
			)
		if ebilanz.report is None:
			frappe.throw(
				_("The E-Bilanz has no instance: {0}").format(
					"; ".join(escape_html(finding.text) for finding in ebilanz.blocking)
				)
			)
		return ebilanz

	def e_bilanz_print(self) -> dict[str, Any]:
		"""The parts of the print format „E-Bilanz“ (layout.print_sections)."""
		return layout.print_sections(
			self._rows(self.LINES),
			self._rows(ACCOUNTS),
			self._rows(FIXED_ASSETS),
			self._rows(TRANSFERS) if self._handelsbilanz else (),
			handelsbilanz=self._handelsbilanz,
			accounting_standard=self.accounting_standard or "",
			revision_status=self.revision_status or "",
		)

	# Berechnen.

	def _structure(self, settings, view: Taxonomy) -> Structure:
		with core_errors():
			case = bridge.case_of(
				settings.legal_form,
				getdate(self.from_date),
				getdate(self.to_date),
				self.statement_type,
				self.accounting_standard,
			)
		return positions.structure(view, case)

	def _mapping(self) -> Document:
		if not frappe.db.exists(MAPPING, self.company):
			frappe.throw(
				_(
					"{0} has no Balance Sheet Mapping. Create one for the company, for example with Steuerbote einrichten, before calculating its E-Bilanz."
				).format(escape_html(self.company))
			)
		return frappe.get_doc(MAPPING, self.company)

	def _placement(
		self, mapping: Document, purpose: Purpose, book: str | None
	) -> tuple[Placement, tuple[str, ...]]:
		"""The books of the E-Bilanz on the positions of the Bilanzzuordnung, and the Period Closing Vouchers of the
		Wirtschaftsjahr."""
		closing = balances.closing_account(self.company)
		books, closed_by = ebilanz_sources.books_of(
			self.company,
			self.fiscal_year,
			getdate(self.from_date),
			self.statement_type,
			finance_book=book,
			closing_account=closing[0] if closing else None,
		)
		return self._place(mapping, books, purpose, closing[1] if closing else None), closed_by

	def _opening_placement(self, mapping: Document, purpose: Purpose, book: str | None) -> Placement:
		closing = balances.closing_account(self.company)
		return self._place(
			mapping,
			ebilanz_sources.opening_books(self.company, getdate(self.from_date), book),
			purpose,
			closing[1] if closing else None,
		)

	def _place(
		self, mapping: Document, books: Books, purpose: Purpose, closing_account: str | None
	) -> Placement:
		"""The books on the positions of the Bilanzzuordnung (Balance Sheet Mapping.place). A mapping on another version
		of the HGB-Taxonomie (SB-ZUORDNUNG-VERSION) has them placed against the fiscal view of the version of the
		E-Bilanz, which Berechnen has read already and which its positions, its „davon“ lines and its Anlagenspiegel
		take, so that the version of the mapping need not be installed; a balance on a position the version of the
		E-Bilanz does not have goes to none, with the finding BILANZ-POSITION."""
		fiscal_year = (getdate(self.from_date), getdate(self.to_date))
		if mapping.taxonomy_version == self.taxonomy_version:
			return mapping.place(books, purpose, closing_account=closing_account, fiscal_year=fiscal_year)
		return place(
			mapping.to_mapping(),
			books,
			eric_settings.taxonomy_view(self.taxonomy_version, View.FISCAL),
			purpose,
			closing_account=closing_account,
			fiscal_year=fiscal_year,
		)

	def _asset_rows(self, mapping: Document, view: Taxonomy) -> list[dict[str, Any]]:
		"""The rows of the Anlagenspiegel: per asset category from the report of ERPNext, in Steuerbilanzwerten, or for a
		Handelsbilanz in Handelsbilanzwerten with the Überleitungswerte the finance book of the Steuerbilanz gives;
		then the rows by hand."""
		stored = self._rows(FIXED_ASSETS)
		days = (getdate(self.from_date), getdate(self.stichtag))
		places = self._asset_positions(mapping, view)
		if not self._handelsbilanz:
			values = ebilanz_sources.book_assets(self.company, *days, self._book())
			rows = bridge.category_rows(bridge.by_category(values.values()), places, "StB", stored)
		else:
			commercial = ebilanz_sources.book_assets(
				self.company, *days, self.commercial_finance_book or None
			)
			rows = bridge.category_rows(bridge.by_category(commercial.values()), places, "HB", stored)
			if self.tax_finance_book:
				tax = ebilanz_sources.book_assets(self.company, *days, self.tax_finance_book)
				rows.extend(
					bridge.category_rows(
						bridge.transfer_values(tax, commercial), places, "Überleitung", stored
					)
				)
		return [*rows, *bridge.rows_by_hand(stored)]

	def _asset_positions(self, mapping: Document, view: Taxonomy) -> dict[str, str | None]:
		"""The position each fixed asset account of the company goes to, by its number: that of its rule in the
		Bilanzzuordnung, where its value counts (steuerbote.xbrl.mapping.position_of); None without a rule."""
		core = mapping.to_mapping()
		found: dict[str, str | None] = {}
		for number in ebilanz_sources.fixed_asset_accounts(self.company).values():
			place = core.place_of(number) if number else None
			concept = getattr(place, "concept", None)
			found[number] = position_of(view, concept) if concept and view.has(concept) else None
		return found

	def _transfer_rows(
		self, mapping: Document, structure: Structure, placement: Placement
	) -> list[dict[str, Any]]:
		"""The entries of the Überleitung of a Handelsbilanz: from the finance book of the Steuerbilanz for a
		Jahresabschluss, then those by hand."""
		stored = self._rows(TRANSFERS)
		if not self._handelsbilanz:
			return []
		derived = ()
		if self.tax_finance_book and not self._opening:
			tax, _closed_by = self._placement(mapping, Purpose.TAX, self.tax_finance_book)
			derived = bridge.derived_transfers(
				structure,
				ebilanz_balances(placement),
				ebilanz_balances(tax),
				ebilanz_balances(
					self._opening_placement(mapping, Purpose.COMMERCIAL, self.commercial_finance_book or None)
				),
				ebilanz_balances(self._opening_placement(mapping, Purpose.TAX, self.tax_finance_book)),
			)
		return bridge.transfer_rows(derived, stored)

	def _previous_equity(
		self,
		structure: Structure,
		mapping: Document,
		purpose: Purpose,
		book: str | None,
		first_year: bool,
		balances_,
		adjustments,
		transfers,
	) -> tuple[Decimal, Decimal]:
		"""The Betriebsvermögen at the end of the previous year and the Einlagen at the founding: in the founding year
		zero and the Eigenkapital of the books on its first day; else what the filed E-Bilanz of the previous year
		reported, or the books at the beginning of the Wirtschaftsjahr, for a Handelsbilanz with the steuerlicher
		Ausgleichsposten of the last Stichtag (Leitfaden B.14.3.2.12)."""
		zero = Decimal("0.00")
		if self._opening:
			return zero, zero
		with core_errors():
			opening = bridge.equity_of(
				structure, ebilanz_balances(self._opening_placement(mapping, purpose, book))
			)
		if first_year:
			return zero, opening
		filed = ebilanz_sources.filed_tax_equity(self.company, cint(self.year) - 1)
		if filed is not None:
			return filed, zero
		if self._handelsbilanz:
			with core_errors():
				transferred = ueberleitung(
					calculate(structure, balances_, adjustments), bridge.transfers_of(transfers)
				)
			return opening + bridge.last_ausgleichsposten(transferred), zero
		return opening, zero

	def _annual_accounts(self) -> str | None:
		"""The Jahresabschluss Berechnen compares the E-Bilanz with: the one it names while that is valid, else the valid
		one of its company and year; an Eröffnungsbilanz has none."""
		if self._opening:
			return None
		return ebilanz_sources.annual_accounts_for_ebilanz(
			self.company, cint(self.year), self.annual_accounts
		)

	def _comparison_findings(self, ebilanz: EBilanz, accounts: str | None) -> tuple[Finding, ...]:
		"""The Handelsbilanz of the E-Bilanz against that of its Jahresabschluss (comparison.py), by the amounts of the
		positions before the Überleitung; an Eröffnungsbilanz is compared with none."""
		if self._opening:
			return ()
		calculation = ebilanz.calculation
		return comparison.findings(
			ebilanz_sources.annual_accounts_comparison(accounts),
			bridge.accounting_standard_of(self.accounting_standard),
			lambda concept: calculation.amount(positions.qualified(concept)),
		)

	def _equity_changes(self, previous: Decimal, founding: Decimal) -> EquityChanges:
		with core_errors():
			return bridge.equity_changes(
				previous,
				override=self.bvv_previous_equity_override,
				override_reason=self.bvv_previous_equity_reason,
				founding=founding,
				contributions=self.bvv_contributions,
				withdrawals=self.bvv_withdrawals,
				adjustments=self.bvv_capital_adjustments,
			)

	def _master(self, settings, first_year: bool):
		return ebilanz_sources.master_data(
			self.company,
			settings,
			revision_status=self.revision_status,
			previous_fiscal_year=None
			if first_year
			else ebilanz_sources.previous_fiscal_year(self.company, getdate(self.from_date)),
			generated=getdate(),
		)

	def _first_year(self) -> bool:
		"""Whether the company was founded within the Wirtschaftsjahr, by its Date of Establishment."""
		founded = date_of_establishment(self.company)
		return founded is not None and getdate(self.from_date) <= founded <= getdate(self.to_date)

	def _settings(self):
		settings = settings_of(self.company)
		if settings is None or not settings.legal_form:
			frappe.throw(
				_("Enter the Annual Filing Settings of {0} with its legal form first.").format(
					escape_html(self.company)
				),
				title=_("Annual Filing Settings"),
			)
		return settings

	def _book(self) -> str | None:
		with core_errors():
			return bridge.balance_book(
				self.accounting_standard, self.commercial_finance_book, self.tax_finance_book
			)

	@property
	def _opening(self) -> bool:
		return self.statement_type == bridge.EROEFFNUNGSBILANZ

	@property
	def _handelsbilanz(self) -> bool:
		return self.accounting_standard == AccountingStandard.HANDELSBILANZ.value

	# The rules of a save.

	def _take_the_finance_books(self) -> None:
		"""A new E-Bilanz takes the finance books of the Annual Filing Settings where it names none."""
		if not self.is_new():
			return
		settings = settings_of(self.company)
		if settings is None:
			return
		for fieldname in ("commercial_finance_book", "tax_finance_book"):
			if not self.get(fieldname):
				self.set(fieldname, settings.get(fieldname))

	def _name_the_annual_accounts(self) -> None:
		"""A new E-Bilanz of a Jahresabschluss names the Jahresabschluss of its company and year that Berechnen compares
		it with, so that the Jahresabschluss lists it among its connections from the start."""
		if self.is_new() and not self._opening:
			self.annual_accounts = ebilanz_sources.annual_accounts_for_ebilanz(
				self.company, cint(self.year), None
			)

	def _keep_the_inputs(self, before: Document | None) -> None:
		"""A save keeps what Berechnen wrote in the Anlagenspiegel and the Überleitung and takes the entries of the
		company; another key discards both with the calculation."""
		if before is None or self.flags.calculating:
			return
		if self._key_of(before) != self._key_of(self):
			self.set(FIXED_ASSETS, [])
			self.set(TRANSFERS, [])
			return
		self.set(FIXED_ASSETS, bridge.kept_assets(self._rows(FIXED_ASSETS, before), self._rows(FIXED_ASSETS)))
		self.set(TRANSFERS, bridge.kept_transfers(self._rows(TRANSFERS, before), self._rows(TRANSFERS)))

	def _take_the_lines_by_hand(self) -> None:
		"""A line by hand, as the base marks a new line, names its position without the prefix of its module, names
		none that Berechnen reports, and takes the label and the component of its position from the installed
		taxonomy."""
		with core_errors():
			kept = bridge.lines_by_hand(self._rows(self.LINES))
		by_hand = [
			(row, values) for row, values in zip(self.get(self.LINES), kept, strict=True) if cint(row.manual)
		]
		view = position_taxonomy(self.taxonomy_version) if by_hand else None
		for row, values in by_hand:
			row.concept = values["concept"]
			concept = positions.qualified(row.concept)
			known = view is not None and view.has(concept)
			part = part_of(view, concept) if known else None
			row.update(
				{
					"label": view.label(concept) if known else None,
					"component": COMPONENTS.get(part.value) if part is not None else None,
				}
			)

	def _require_berechnen_after_a_change(self, before: Document | None) -> None:
		"""A calculated E-Bilanz whose basis, Betriebsvermögensvergleich, Anlagenspiegel or Überleitung by hand changed
		is Berechnet again, with a finding that asks for Berechnen."""
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
				"An entry that Berechnen reads changed since Berechnen: the basis of the E-Bilanz, the Betriebsvermögensvergleich, a column or row by hand of the Anlagenspiegel or an entry by hand of the Überleitung. Calculate again, so that Berechnen checks the E-Bilanz with it."
			),
		)
		self.set(FINDINGS_TABLE, annual_findings.rows((*stored, recalculate)))

	# Helpers.

	def _form_state(self) -> dict[str, Any]:
		"""For the form: whether XBRL exportieren gives a file, which a calculated draft and a filed E-Bilanz do."""
		calculated = self.docstatus == 0 and self.status in self.LIFECYCLE.calculated
		filed = self.docstatus == 1 and self.status in self.LIFECYCLE.filings
		return {"export": bool(calculated or filed)}

	def _file_name(self) -> str:
		company = re.sub(r"[^\w]+", "-", self.company).strip("-")
		return f"E-Bilanz-{company}-{getdate(self.stichtag).isoformat()}.xml"

	def _attach(self, file_name: str, content: bytes) -> str:
		"""Attach the file privately; a file of the same content attached before is kept instead."""
		attached = frappe.db.get_value(
			"File",
			{
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"content_hash": get_content_hash(content),
			},
			"file_url",
		)
		if attached:
			return attached
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"is_private": 1,
				"content": content,
			}
		)
		file.insert()
		return file.file_url

	def _rows(self, table: str, doc: Document | None = None) -> list[dict[str, Any]]:
		return [row.as_dict() for row in (doc or self).get(table) or ()]


@contextmanager
def core_errors() -> Iterator[None]:
	"""Show what the bridge and the core of the E-Bilanz refuse as a message in the language of the user."""
	try:
		yield
	except bridge.BridgeError as error:
		values = [_(value) if value in bridge.TABLES else escape_html(str(value)) for value in error.values]
		frappe.throw(_(error.template).format(*values), title=_(DOCTYPE))
	except (CaseError, OverrideError) as error:
		frappe.throw(escape_html(str(error)), title=_(DOCTYPE))


def _inputs(doc: Document) -> tuple:
	"""What Berechnen reads of the document besides its positions, comparable between two states of it."""
	return bridge.inputs(
		{fieldname: doc.get(fieldname) for fieldname in bridge.INPUT_FIELDS},
		[row.as_dict() for row in doc.get(FIXED_ASSETS) or ()],
		[row.as_dict() for row in doc.get(TRANSFERS) or ()],
	)
