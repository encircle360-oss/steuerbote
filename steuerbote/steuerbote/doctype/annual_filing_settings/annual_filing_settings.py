"""The Annual Filing Settings of a company: what its year-end filings read beyond the ledger.

The rules are in annual_filing_settings/rules.py. This controller reads the rows into the values of the rules,
fills what the company and the VAT Return Settings already say, and refuses what the forms would not take. The
Steuernummern and Identifikationsnummern of the shareholders have permlevel 1, and the DocType keeps no versions,
so that these numbers reach neither a user without the right to read them nor a log (§ 139b Abs. 2 AO).
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from enum import StrEnum

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, escape_html, flt, formatdate, getdate

from steuerbote.elster import SCHEMES, STATE_CODES, SteuernummerError, to_elster
from steuerbote.steuerbote.doctype.annual_filing_settings import rules

REGISTER_FIELDS = ("register_court", "register_type", "register_number")
# A Period Closing Voucher closes the result only into such an account (check_closing_account of ERPNext 16).
CLOSING_ROOT_TYPES = ("Liability", "Equity")


class AnnualFilingSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.annual_filing_carry_forward.annual_filing_carry_forward import (
			AnnualFilingCarryForward,
		)
		from steuerbote.steuerbote.doctype.annual_filing_director.annual_filing_director import (
			AnnualFilingDirector,
		)
		from steuerbote.steuerbote.doctype.annual_filing_employment_type.annual_filing_employment_type import (
			AnnualFilingEmploymentType,
		)
		from steuerbote.steuerbote.doctype.annual_filing_establishment.annual_filing_establishment import (
			AnnualFilingEstablishment,
		)
		from steuerbote.steuerbote.doctype.annual_filing_holding.annual_filing_holding import (
			AnnualFilingHolding,
		)
		from steuerbote.steuerbote.doctype.annual_filing_prepayment.annual_filing_prepayment import (
			AnnualFilingPrepayment,
		)
		from steuerbote.steuerbote.doctype.annual_filing_shareholder.annual_filing_shareholder import (
			AnnualFilingShareholder,
		)
		from steuerbote.steuerbote.doctype.annual_filing_size_class.annual_filing_size_class import (
			AnnualFilingSizeClass,
		)
		from steuerbote.steuerbote.doctype.annual_filing_trade_tax_rate.annual_filing_trade_tax_rate import (
			AnnualFilingTradeTaxRate,
		)
		from steuerbote.steuerbote.doctype.annual_filing_year.annual_filing_year import AnnualFilingYear

		accounting_standard: DF.Literal["HAOE", "HGBM", "AO"]
		address_supplement: DF.Data | None
		advisor_clerk: DF.Data | None
		advisor_client_number: DF.Data | None
		advisor_details: DF.Data | None
		advisor_first_name: DF.Data | None
		advisor_name: DF.Data | None
		advisor_phone: DF.Data | None
		advisor_street: DF.Data | None
		advisor_town: DF.Data | None
		business_purpose: DF.Data | None
		carry_forwards: DF.Table[AnnualFilingCarryForward]
		city: DF.Data | None
		closing_account: DF.Link | None
		commercial_finance_book: DF.Link | None
		company: DF.Link
		country: DF.Link | None
		directors: DF.Table[AnnualFilingDirector]
		elster_income_tax_number: DF.Data | None
		establishments: DF.Table[AnnualFilingEstablishment]
		excluded_employment_types: DF.Table[AnnualFilingEmploymentType]
		holding_267a_3: DF.Check
		holdings: DF.Table[AnnualFilingHolding]
		house_number: DF.Data | None
		house_number_suffix: DF.Data | None
		income_tax_number: DF.Data | None
		income_tax_review_note: DF.SmallText | None
		income_tax_review_on: DF.Date | None
		kleinst_mode: DF.Literal["Hinterlegung", "Veröffentlichung"]
		legal_form: DF.Literal["", "GmbH", "UG"]
		management_seat: DF.Data | None
		postal_code: DF.Data | None
		prepayments: DF.Table[AnnualFilingPrepayment]
		register_court: DF.Data | None
		register_number: DF.Data | None
		register_type: DF.Literal["", "HRA", "HRB", "GnR", "PR", "VR"]
		registered_seat: DF.Data | None
		section_8b_7: DF.Check
		section_8b_7_confirmed_on: DF.Date | None
		section_8b_7_note: DF.SmallText | None
		shareholders: DF.Table[AnnualFilingShareholder]
		size_history: DF.Table[AnnualFilingSizeClass]
		street: DF.Data | None
		tax_finance_book: DF.Link | None
		trade_tax_rates: DF.Table[AnnualFilingTradeTaxRate]
		years: DF.Table[AnnualFilingYear]
	# end: auto-generated types

	def validate(self) -> None:
		self.set_register()
		self.set_elster_income_tax_number()
		self.keep_adoption_dates()
		with settings_errors():
			self.normalize_identifiers()
			self.check_texts()
			self.get_address()
			for table, check in self.table_checks().items():
				if self.is_complete(table):
					check()
		self.check_closing_account()
		self.check_employment_types()
		self.sort_tables()

	def table_checks(self) -> dict[str, Callable[[], None]]:
		"""The checks of each table, which read every row of it."""
		return {
			"years": lambda: rules.check_years(self.get_years()),
			"shareholders": lambda: rules.check_shareholders(self.get_shareholders()),
			"directors": lambda: rules.check_directors(self.get_directors()),
			"establishments": lambda: rules.check_establishments(self.get_establishments()),
			"trade_tax_rates": lambda: rules.check_trade_tax_rates(self.get_trade_tax_rates()),
			"holdings": lambda: rules.check_holdings(self.get_holdings()),
			"prepayments": lambda: rules.check_prepayments(self.get_prepayments()),
			"carry_forwards": lambda: rules.check_carry_forwards(self.get_carry_forwards()),
			"size_history": lambda: rules.check_size_history(self.get_size_history()),
			"excluded_employment_types": lambda: rules.check_employment_types(
				self.employment_types_not_counted()
			),
		}

	def is_complete(self, table: str) -> bool:
		"""Whether every row of a table has its mandatory values. Saving checks them only after validate, and that check
		names a row that lacks one, so the rules of a table wait for it."""
		meta = frappe.get_meta(self.meta.get_field(table).options)
		required = [field.fieldname for field in meta.fields if field.reqd]
		return all(cstr(row.get(name)).strip() for row in self.get(table) for name in required)

	def set_register(self) -> None:
		"""Fill an empty register field from the company, where the app erpnext_germany gives it these fields."""
		if not self.company:
			return
		for fieldname, value in company_register(self.company).items():
			if value and not self.get(fieldname):
				self.set(fieldname, value)

	def set_elster_income_tax_number(self) -> None:
		"""The 13-digit form of the Steuernummer for KSt and GewSt, in the Bundesland of the VAT Return Settings."""
		number = cstr(self.income_tax_number).strip()
		self.income_tax_number = number or None
		if not number:
			self.elster_income_tax_number = None
			return
		state = frappe.db.get_value("VAT Return Settings", self.company, "state") if self.company else None
		code = STATE_CODES.get(state)
		if code is None:
			frappe.throw(
				_(
					"The Steuernummer for KSt and GewSt takes the format of the Bundesland of the VAT Return Settings, "
					"which {0} does not have yet."
				).format(escape_html(cstr(self.company))),
				title=_("Annual Filing Settings"),
			)
		try:
			self.elster_income_tax_number = to_elster(code, number)
		except SteuernummerError:
			frappe.throw(
				_("The Steuernummer {0} does not have the format {1} of {2}.").format(
					escape_html(number), SCHEMES[code].standard, state
				),
				title=_("Invalid Steuernummer"),
			)

	def keep_adoption_dates(self) -> None:
		"""Only the Jahresabschluss writes the day of its Feststellung, through record_adoption: a save keeps the stored
		day, and a year that holds one keeps its row."""
		if self.flags.recording_adoption:
			return
		before = self.get_doc_before_save()
		stored = {
			cint(row.year): row.adopted_on for row in (before.years if before else []) if row.adopted_on
		}
		kept = {cint(row.year) for row in self.years}
		for year in sorted(set(stored) - kept):
			frappe.throw(
				_(
					"The year {0} holds the Feststellung of its Jahresabschluss on {1}, which only cancelling the "
					"Jahresabschluss removes."
				).format(year, formatdate(stored[year])),
				title=_("Annual Filing Settings"),
			)
		for row in self.years:
			row.adopted_on = stored.get(cint(row.year))

	def normalize_identifiers(self) -> None:
		"""Keep the numbers as the forms take them: without blanks, the W-IdNr. in capitals."""
		for row in self.shareholders:
			row.idnr = rules.normalized_idnr(row.idnr, row.idx)
			row.wid_nr = rules.normalized_wid_nr(row.wid_nr, row.idx)
			rules.elster_tax_number(row.tax_number, row.tax_number_state, row.idx)
		for row in (*self.establishments, *self.trade_tax_rates, *self.prepayments):
			row.ags = rules.normalized_ags(row.ags) if cstr(row.ags).strip() else None

	def check_texts(self) -> None:
		"""Refuse a text that the forms would not take, before a filing reads it."""
		for fieldname, length in rules.TEXT_LENGTHS.items():
			rules.elster_text(self.get(fieldname), _(self.meta.get_label(fieldname)), length)
		for table, lengths in rules.ROW_TEXT_LENGTHS.items():
			table_label = _(self.meta.get_label(table))
			meta = frappe.get_meta(self.meta.get_field(table).options)
			for row in self.get(table):
				for fieldname, length in lengths.items():
					label = _("{0} in row {1} of {2}").format(
						_(meta.get_label(fieldname)), row.idx, table_label
					)
					rules.elster_text(row.get(fieldname), label, length)

	def check_closing_account(self) -> None:
		"""The closing account is one that a Period Closing Voucher of the company takes."""
		if not self.closing_account:
			return
		account = frappe.db.get_value(
			"Account", self.closing_account, ["company", "root_type", "is_group", "disabled"], as_dict=True
		)
		if (
			not account
			or account.company != self.company
			or account.root_type not in CLOSING_ROOT_TYPES
			or account.is_group
			or account.disabled
		):
			frappe.throw(
				_(
					"The closing account {0} must be a Liability or Equity account of {1} that takes postings, as the "
					"Period Closing Voucher requires."
				).format(escape_html(self.closing_account), escape_html(cstr(self.company))),
				title=_("Annual Filing Settings"),
			)

	def check_employment_types(self) -> None:
		"""Where HRMS is installed, the Employment Types listed exist."""
		if not frappe.db.exists("DocType", "Employment Type"):
			return
		for name in self.employment_types_not_counted():
			if not frappe.db.exists("Employment Type", name):
				frappe.throw(
					_("There is no Employment Type {0}.").format(escape_html(name)),
					title=_("Annual Filing Settings"),
				)

	def sort_tables(self) -> None:
		"""Keep the rows of the tables by year in the order of their years, whatever order they were entered in."""
		for table, key in (
			("years", lambda row: cint(row.year)),
			("trade_tax_rates", lambda row: (cstr(row.ags), cint(row.year))),
			("holdings", lambda row: (cint(row.year), cstr(row.holding_name).casefold())),
			("prepayments", lambda row: (cint(row.year), cstr(row.due_date), cstr(row.tax))),
			("carry_forwards", lambda row: (cstr(row.as_of), cstr(row.kind))),
			("size_history", lambda row: cstr(row.fiscal_year_end)),
		):
			self.get(table).sort(key=key)
			for index, row in enumerate(self.get(table), start=1):
				row.idx = index

	@frappe.whitelist(methods=["POST"])
	def fill_address(self, quiet: bool = False) -> None:
		"""Put the address of the VAT Return Settings into the form, with the street split at its last digits.

		Nothing is stored: the form shows the proposal, and saving it confirms it. ``quiet`` proposes nothing and
		says nothing when the company has no VAT Return Settings, as the form does for a new document.
		"""
		if not self.company:
			frappe.throw(_("Select the company first."))
		if not frappe.db.exists("VAT Return Settings", self.company) or not frappe.has_permission(
			"VAT Return Settings", "read", doc=self.company
		):
			if quiet:
				return
			frappe.throw(
				_("The company {0} has no VAT Return Settings to take the address from.").format(
					escape_html(self.company)
				),
				title=_("Annual Filing Settings"),
			)
		source = frappe.db.get_value(
			"VAT Return Settings", self.company, ["street", "postal_code", "city"], as_dict=True
		)
		split = rules.split_street(source.street)
		self.update(
			{
				"street": split.street if split else None,
				"house_number": split.house_number if split else None,
				"house_number_suffix": split.house_number_suffix if split else None,
				"postal_code": source.postal_code,
				"city": source.city,
			}
		)

	def record_adoption(self, year: int, adopted_on: date | None) -> None:
		"""Write the day the shareholders adopted the Jahresabschluss of the fiscal year ending in ``year``, or clear it
		with None. The Jahresabschluss calls it on submit and on cancel, after its own permission check."""
		row = next((row for row in self.years if cint(row.year) == year), None)
		if row is None:
			row = self.append("years", {"year": year})
		row.adopted_on = adopted_on
		self.flags.recording_adoption = True
		try:
			self.save(ignore_permissions=True)
		finally:
			self.flags.recording_adoption = False

	def elster_tax_number(self) -> str | None:
		"""The 13-digit Steuernummer of the Körperschaft- and Gewerbesteuererklärung and of the E-Bilanz: that of these
		settings when they have one, else that of the VAT Return Settings."""
		return self.elster_income_tax_number or frappe.db.get_value(
			"VAT Return Settings", self.company, "elster_tax_number"
		)

	def rechtsform(self) -> str:
		with settings_errors():
			return rules.rechtsform(self.legal_form)

	def legal_status(self, *, disclosure: bool = False) -> str:
		with settings_errors():
			return rules.legal_status(self.legal_form, disclosure=disclosure)

	def get_address(self) -> rules.Address:
		with settings_errors():
			return rules.Address(
				street=_text(self.street),
				house_number=_text(self.house_number),
				house_number_suffix=_text(self.house_number_suffix),
				supplement=_text(self.address_supplement),
				postal_code=_text(self.postal_code),
				city=_text(self.city),
				country=self.country or rules.GERMANY,
			)

	def get_years(self) -> list[rules.YearSettings]:
		with settings_errors():
			return [
				rules.YearSettings(
					cint(row.year),
					advisor_prepares=bool(cint(row.advisor_prepares)),
					kleinunternehmer=bool(cint(row.kleinunternehmer)),
					early_request_ust=_date(row.early_request_ust),
					early_request_kst=_date(row.early_request_kst),
					early_request_gewst=_date(row.early_request_gewst),
					adopted_on=_date(row.adopted_on),
					exempt_264_3=bool(cint(row.exempt_264_3)),
					exempt_264_3_reason=_text(row.exempt_264_3_reason),
					no_vat_return=bool(cint(row.no_vat_return)),
					no_vat_return_reason=_text(row.no_vat_return_reason),
					no_vat_return_note=_text(row.no_vat_return_note),
				)
				for row in self.years
			]

	def year_settings(self, year: int) -> rules.YearSettings | None:
		return rules.year_settings(self.get_years(), year)

	def get_shareholders(self) -> list[rules.Shareholder]:
		"""The shareholders with their Steuernummer for ELSTER. The numbers are for the KSt 1 alone; never log them."""
		with settings_errors():
			return [
				rules.Shareholder(
					row=row.idx,
					name=row.shareholder_name,
					kind=row.kind,
					nominal_amount=_decimal(row.nominal_amount),
					percent=_decimal(row.percent),
					from_date=getdate(row.from_date),
					to_date=_date(row.to_date),
					tax_number=rules.elster_tax_number(row.tax_number, row.tax_number_state, row.idx),
					idnr=rules.normalized_idnr(row.idnr, row.idx),
					wid_nr=rules.normalized_wid_nr(row.wid_nr, row.idx),
					foreign_id=_text(row.foreign_id),
					street=_text(row.street),
					postal_code_and_town=_text(row.postal_code_and_town),
				)
				for row in self.shareholders
			]

	def get_directors(self) -> list[rules.Director]:
		with settings_errors():
			return [
				rules.Director(
					row=row.idx,
					name=row.director_name,
					from_date=getdate(row.from_date),
					to_date=_date(row.to_date),
					role=_text(row.role),
					is_shareholder=bool(cint(row.is_shareholder)),
					signs=bool(cint(row.signs)),
				)
				for row in self.directors
			]

	def get_establishments(self) -> list[rules.Establishment]:
		with settings_errors():
			return [
				rules.Establishment(
					row=row.idx,
					municipality=row.municipality,
					postal_code=cstr(row.postal_code).strip(),
					ags=row.ags,
					from_date=getdate(row.from_date),
					to_date=_date(row.to_date),
					hebenummer=_text(row.hebenummer),
				)
				for row in self.establishments
			]

	def get_trade_tax_rates(self) -> list[rules.TradeTaxRate]:
		with settings_errors():
			return [
				rules.TradeTaxRate(
					ags=row.ags,
					year=cint(row.year),
					hebesatz=_decimal(row.hebesatz),
					source=row.source,
					source_date=_date(row.source_date),
				)
				for row in self.trade_tax_rates
			]

	def hebesatz(self, ags: str, year: int) -> rules.TradeTaxRate | None:
		return rules.hebesatz_of(self.get_trade_tax_rates(), ags, year)

	def get_holdings(self) -> list[rules.Holding]:
		with settings_errors():
			return [
				rules.Holding(
					name=row.holding_name,
					year=cint(row.year),
					percent_on_1_january=_optional_decimal(row.percent_on_1_january),
					percent_at_start_of_ez=_optional_decimal(row.percent_at_start_of_ez),
					bought_on=_date(row.bought_on),
					sold_on=_date(row.sold_on),
					identifier=_text(row.identifier),
					country=row.country or None,
				)
				for row in self.holdings
			]

	def get_prepayments(self) -> list[rules.Prepayment]:
		with settings_errors():
			return [
				rules.Prepayment(
					tax=row.tax,
					year=cint(row.year),
					due_date=getdate(row.due_date),
					amount=_decimal(row.amount),
					notice_date=_date(row.notice_date),
					ags=_text(row.ags),
				)
				for row in self.prepayments
			]

	def get_carry_forwards(self) -> list[rules.CarryForward]:
		with settings_errors():
			return [
				rules.CarryForward(
					kind=row.kind,
					as_of=getdate(row.as_of),
					amount=_decimal(row.amount),
					notice_date=_date(row.notice_date),
					confirmed=bool(cint(row.confirmed)),
				)
				for row in self.carry_forwards
			]

	def get_size_history(self) -> list[rules.SizeRecord]:
		with settings_errors():
			return [
				rules.SizeRecord(
					fiscal_year_end=getdate(row.fiscal_year_end),
					size_class=row.size_class,
					source=row.source,
					balance_sheet_total=_optional_decimal(row.balance_sheet_total),
					revenue=_optional_decimal(row.revenue),
					employees=_optional_decimal(row.employees),
					reason=_text(row.reason),
				)
				for row in self.size_history
			]

	def employment_types_not_counted(self) -> list[str]:
		"""The Employment Types whose employees stay out of the headcount of § 267 Abs. 5 HGB."""
		return [cstr(row.employment_type).strip() for row in self.excluded_employment_types]


def company_register(company: str) -> dict[str, str | None]:
	"""Register court, type and number of a company, as the custom fields of erpnext_germany hold them; nothing
	without that app."""
	meta = frappe.get_meta("Company")
	present = [fieldname for fieldname in REGISTER_FIELDS if meta.has_field(fieldname)]
	if not present:
		return {}
	return frappe.db.get_value("Company", company, present, as_dict=True) or {}


def settings_of(company: str) -> AnnualFilingSettings | None:
	"""The Annual Filing Settings of a company, or None when it has none."""
	if not frappe.db.exists("Annual Filing Settings", company):
		return None
	return frappe.get_doc("Annual Filing Settings", company)


def record_adoption(company: str, year: int, adopted_on: date | None) -> None:
	"""Write or clear the Feststellung of the Jahresabschluss of ``year`` in the settings of the company."""
	settings = settings_of(company)
	if settings is None:
		frappe.throw(
			_("Enter the Annual Filing Settings of {0} first.").format(escape_html(company)),
			title=_("Annual Filing Settings"),
		)
	settings.record_adoption(year, adopted_on)


@contextmanager
def settings_errors() -> Iterator[None]:
	"""Show a broken rule as a message in the language of the user, with the options it names translated."""
	try:
		yield
	except rules.SettingsError as error:
		values = [
			_(str(value))
			if isinstance(value, StrEnum)
			else escape_html(value)
			if isinstance(value, str)
			else value
			for value in error.values
		]
		frappe.throw(_(error.template).format(*values), title=_("Annual Filing Settings"))


def _text(value: object) -> str | None:
	return cstr(value).strip() or None


def _date(value: object) -> date | None:
	"""A date field as a date; getdate of nothing would give today."""
	return getdate(value) if value else None


def _decimal(value: object) -> Decimal:
	return Decimal(str(flt(value)))


def _optional_decimal(value: object) -> Decimal | None:
	return None if value is None or value == "" else _decimal(value)
