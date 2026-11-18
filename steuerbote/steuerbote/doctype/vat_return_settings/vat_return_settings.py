from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, escape_html, flt

from steuerbote.elster import SCHEMES, STATE_CODES, SteuernummerError, to_elster, ustva_xml
from steuerbote.steuerbote.doctype.vat_return import bridge
from steuerbote.steuerbote.doctype.vat_return_settings import rules
from steuerbote.ustva import Rhythm


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

		chart: DF.Literal["SKR03", "SKR04", "Eigener Kontenrahmen"]
		city: DF.Data | None
		company: DF.Link
		comparison_threshold_amount: DF.Currency
		comparison_threshold_percent: DF.Percent
		elster_tax_number: DF.Data | None
		email: DF.Data | None
		filer_name: DF.Data | None
		period_rules: DF.Table[VATReturnPeriodRule]
		phone: DF.Data | None
		postal_code: DF.Data | None
		prepayments: DF.Table[VATReturnPrepayment]
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
		street: DF.Data | None
		tax_number: DF.Data
		tax_office: DF.Data | None
		taxation_type: DF.Literal["Soll"]
		tolerance: DF.Currency
		wid_nr: DF.Data | None
	# end: auto-generated types

	def validate(self) -> None:
		self.set_elster_tax_number()
		self.check_for_elster()
		self.sort_period_rules()
		with settings_errors():
			rules.check_period_rules(self.get_period_rules())
			rules.check_prepayments(self.get_prepayments())

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

	def check_for_elster(self) -> None:
		"""Refuse a W-IdNr. or a Datenlieferant that ELSTER would not take, before the first file is made."""
		with xml_errors(_("VAT Return Settings")):
			self.wid_nr = ustva_xml.normalized_wid_nr(self.wid_nr)
			for attribute, field in ustva_xml.DATENLIEFERANT.items():
				ustva_xml.elster_text(
					self.get(bridge.DATENLIEFERANT_FIELDS[attribute]), field.label, field.length
				)

	def sort_period_rules(self) -> None:
		self.period_rules.sort(key=lambda row: (cint(row.year), cint(row.valid_from_month)))
		for index, row in enumerate(self.period_rules, start=1):
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

	def get_prepayments(self) -> list[rules.Prepayment]:
		return [
			rules.Prepayment(
				cint(row.year),
				dauerfristverlaengerung=bool(cint(row.dauerfristverlaengerung)),
				sondervorauszahlung=Decimal(str(flt(row.sondervorauszahlung))),
			)
			for row in self.prepayments
		]


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
