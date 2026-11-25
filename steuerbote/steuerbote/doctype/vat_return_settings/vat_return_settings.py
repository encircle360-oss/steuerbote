from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import get_default_address
from frappe.model.document import Document
from frappe.utils import cint, escape_html, flt, getdate

from steuerbote import prior_filings
from steuerbote.elster import SCHEMES, STATE_CODES, SteuernummerError, to_elster, ustva_xml, zm_xml
from steuerbote.setup import start
from steuerbote.steuerbote.doctype.vat_return import bridge
from steuerbote.steuerbote.doctype.vat_return_settings import rules
from steuerbote.ustva import Rhythm
from steuerbote.zm.rhythm import Rule as ZmRule


class VATReturnSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.vat_return_period_rule.vat_return_period_rule import (
			VATReturnPeriodRule,
		)
		from steuerbote.steuerbote.doctype.vat_return_prepayment.vat_return_prepayment import (
			VATReturnPrepayment,
		)
		from steuerbote.steuerbote.doctype.zm_rule.zm_rule import ZMRule

		books_start: DF.Date | None
		chart: DF.Literal["SKR03", "SKR04", "Eigener Kontenrahmen"]
		city: DF.Data | None
		company: DF.Link
		comparison_threshold_amount: DF.Currency
		comparison_threshold_percent: DF.Percent
		deadline_recipients: DF.SmallText | None
		elster_tax_number: DF.Data | None
		email: DF.Data | None
		filer_name: DF.Data | None
		late_documents: DF.Literal["Corrected Return", "Current Period"]
		max_confirmation_age: DF.Int
		period_basis: DF.Literal["By Service Date", "By Posting Date"]
		period_rules: DF.Table[VATReturnPeriodRule]
		phone: DF.Data | None
		postal_code: DF.Data | None
		prepayments: DF.Table[VATReturnPrepayment]
		reminder_days: DF.Int
		state: DF.Literal[
			"",
			"Baden-Württemberg",
			"Bayern",
			"Berlin",
			"Brandenburg",
			"Bremen",
			"Hamburg",
			"Hessen",
			"Mecklenburg-Vorpommern",
			"Niedersachsen",
			"Nordrhein-Westfalen",
			"Rheinland-Pfalz",
			"Saarland",
			"Sachsen",
			"Sachsen-Anhalt",
			"Schleswig-Holstein",
			"Thüringen",
		]
		statutory_tax: DF.Literal["From the Base in Full Euros", "As Booked"]
		street: DF.Data | None
		tax_number: DF.Data
		tax_office: DF.Data | None
		taxation_type: DF.Literal["Soll"]
		teilnehmernummer: DF.Data | None
		tolerance: DF.Currency
		ust_idnr: DF.Data | None
		vat_id_check_on_change: DF.Check
		vat_id_check_suppliers: DF.Check
		vat_id_goods_max_age: DF.Int
		vat_id_invoice_goods: DF.Literal["Block", "Warn", "Off"]
		vat_id_invoice_services: DF.Literal["Block", "Warn", "Off"]
		vat_id_renewal: DF.Check
		wid_nr: DF.Data | None
		zm_rules: DF.Table[ZMRule]
	# end: auto-generated types

	def validate(self) -> None:
		self.set_elster_tax_number()
		self.set_datenlieferant()
		self.check_for_elster()
		self.set_ust_idnr()
		self.set_teilnehmernummer()
		self.sort_period_rules()
		self.sort_zm_rules()
		with settings_errors():
			rules.check_period_rules(self.get_period_rules())
			rules.check_prepayments(self.get_prepayments())
			rules.check_zm_rules(self.get_zm_rules())
		self.check_books_start()

	def check_books_start(self) -> None:
		"""The books start on the first day of a month (steuerbote/setup/start.py), after no period a VAT Return filed
		through Steuerbote holds and on no period entered as filed before Steuerbote."""
		if not self.books_start:
			return
		day = getdate(self.books_start)
		try:
			start.check_start(day)
		except start.StartError as error:
			frappe.throw(_(error.template).format(*error.values))
		filed = frappe.get_all(
			"VAT Return",
			filters={"company": self.company, "docstatus": 1, "from_date": ["<", day]},
			fields=["name", "period_label"],
			order_by="from_date desc",
			limit=1,
		)
		if filed:
			frappe.throw(
				_(
					"{0} files {1} through Steuerbote, so the books of the company cannot start after it."
				).format(filed[0].name, filed[0].period_label)
			)
		later = [
			filed
			for filed in prior_filings.prior_filings(self.company)
			if not start.before_start(filed.period.start, day)
		]
		if later:
			frappe.throw(
				_(
					"{0} enters {1} as filed before Steuerbote: the books of the company start after that period."
				).format(later[0].name, later[0].period.label)
			)

	def set_elster_tax_number(self) -> None:
		"""A missing state or number is reported by the mandatory check, which runs after validate."""
		state = STATE_CODES.get(self.state)
		if state is None or not self.tax_number:
			self.elster_tax_number = None
			return
		try:
			self.elster_tax_number = to_elster(state, self.tax_number)
		except SteuernummerError:
			frappe.throw(
				_("The Steuernummer {0} does not have the format {1} of {2}.").format(
					escape_html(self.tax_number), SCHEMES[state].standard, self.state
				),
				title=_("Invalid Steuernummer"),
			)

	def set_datenlieferant(self) -> None:
		"""Fill an empty part of the Datenlieferant from the company and its address; what the user entered stays."""
		if self.company:
			self.update(bridge.datenlieferant_defaults(self, company_contact(self.company)))

	def check_for_elster(self) -> None:
		"""Refuse a W-IdNr. or a Datenlieferant that ELSTER would not take, before the first file is made."""
		with xml_errors(_("VAT Return Settings")):
			self.wid_nr = ustva_xml.normalized_wid_nr(self.wid_nr)
			for attribute, field in ustva_xml.DATENLIEFERANT.items():
				ustva_xml.elster_text(
					self.get(bridge.DATENLIEFERANT_FIELDS[attribute]), field.label, field.length
				)

	def set_ust_idnr(self) -> None:
		"""The company's own USt-IdNr., or else its Tax ID when that is a German USt-IdNr."""
		tax_id = frappe.db.get_value("Company", self.company, "tax_id") if self.company else None
		with settings_errors():
			self.ust_idnr = rules.own_vat_id(self.ust_idnr, tax_id)

	def set_teilnehmernummer(self) -> None:
		"""The Teilnehmernummer the BZSt assigned for the Zusammenfassende Meldung, as its Nutzdaten write it."""
		with xml_errors(_("VAT Return Settings")):
			self.teilnehmernummer = zm_xml.teilnehmernummer(self.teilnehmernummer)

	def sort_period_rules(self) -> None:
		self.period_rules.sort(key=lambda row: (cint(row.year), cint(row.valid_from_month)))
		for index, row in enumerate(self.period_rules, start=1):
			row.idx = index

	def sort_zm_rules(self) -> None:
		self.zm_rules.sort(key=lambda row: (cint(row.year), cint(row.valid_from_month)))
		for index, row in enumerate(self.zm_rules, start=1):
			row.idx = index

	def rhythm_for(self, year: int, month: int) -> Rhythm:
		"""The Voranmeldungszeitraum of a month."""
		with settings_errors():
			return rules.rhythm_for(self.get_period_rules(), year, month)

	def has_dauerfrist(self, year: int) -> bool:
		"""Whether the Dauerfristverlängerung moves the deadlines of the year by one month."""
		with settings_errors():
			return rules.has_dauerfrist(self.get_prepayments(), year)

	def sondervorauszahlung(self, year: int) -> Decimal:
		"""The Sondervorauszahlung of the year, deducted in Kz 39 of its last Voranmeldung."""
		with settings_errors():
			return rules.sondervorauszahlung(self.get_prepayments(), year)

	def get_period_rules(self) -> list[rules.PeriodRule]:
		return [
			rules.PeriodRule(cint(row.year), row.rhythm, cint(row.valid_from_month))
			for row in self.period_rules
		]

	def get_zm_rules(self) -> list[ZmRule]:
		"""The rhythm of the Zusammenfassende Meldung as the rules of steuerbote.zm.rhythm."""
		with settings_errors():
			return [
				rules.zm_rule(
					cint(row.year), cint(row.valid_from_month), row.rhythm, bool(cint(row.services_monthly))
				)
				for row in self.zm_rules
			]

	def get_prepayments(self) -> list[rules.Prepayment]:
		return [
			rules.Prepayment(
				cint(row.year),
				dauerfristverlaengerung=bool(cint(row.dauerfristverlaengerung)),
				sondervorauszahlung=Decimal(str(flt(row.sondervorauszahlung))),
			)
			for row in self.prepayments
		]


def company_contact(company: str) -> dict[str, str | None]:
	"""The name, phone and email of a company and the street, postal code and town of its address, under the
	names of the Datenlieferant; phone and email come from the address where the company has none.

	The address is the one get_default_address of Frappe picks among those linked to the company: its primary
	address, else any of them.
	"""
	record = frappe.db.get_value("Company", company, ["company_name", "phone_no", "email"], as_dict=True)
	name = get_default_address("Company", company)
	address = (
		frappe.db.get_value(
			"Address", name, ["address_line1", "pincode", "city", "phone", "email_id"], as_dict=True
		)
		if name
		else None
	)
	record, address = record or {}, address or {}
	return {
		"name": record.get("company_name"),
		"street": address.get("address_line1"),
		"postal_code": address.get("pincode"),
		"city": address.get("city"),
		"phone": record.get("phone_no") or address.get("phone"),
		"email": record.get("email") or address.get("email_id"),
	}


@contextmanager
def settings_errors() -> Iterator[None]:
	"""Show a broken rule as a message in the language of the user."""
	try:
		yield
	except rules.SettingsError as error:
		frappe.throw(_(error.template).format(*error.values), title=_("VAT Return Settings"))


@contextmanager
def xml_errors(title: str) -> Iterator[None]:
	"""Show a value that ELSTER does not take as a message in the language of the user."""
	try:
		yield
	except ustva_xml.XmlError as error:
		label = _(error.label) if error.label else ""
		frappe.throw(_(error.template).format(*error.values, label=label), title=title)
