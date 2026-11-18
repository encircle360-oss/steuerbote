"""VAT Return: the Umsatzsteuer-Voranmeldung of one company for one Voranmeldungszeitraum.

"Berechnen" (calculate) reads the period's general ledger through steuerbote.ledger, the company's VAT
Return Mapping and VAT Return Settings, and leaves every amount to the core in steuerbote.ustva; bridge.py
maps the results onto the tables. A company can switch between monthly and quarterly filing at the start of
a quarter, so a period number alone names a month or a quarter: the return carries its rhythm, which has to
be the one the settings prescribe for the first month of the period. An override replaces a computed amount
once it has a reason, and the totals and Kz 83 always follow the amounts as filed. A period is filed once;
every further return for it is a corrected return (Kz 10), and filing one marks the returns before it as
replaced.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from steuerbote import ustva
from steuerbote.ledger import account_names, accounts_without_number, load_lines
from steuerbote.steuerbote.doctype.vat_return import bridge

SETTINGS_DOCTYPE = "VAT Return Settings"
MAPPING_DOCTYPE = "VAT Return Mapping"

DRAFT = "Entwurf"
CALCULATED = "Berechnet"
READY = "Bereit"
FILED = "Abgegeben"
REPLACED = "Ersetzt"

PERIOD_FIELDS = ("company", "year", "rhythm", "period_index")
CALCULATED_TABLES = ("kennzahlen", "checks", "deviations", "unmapped")


class VATReturn(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.vat_return_check.vat_return_check import VATReturnCheck
		from steuerbote.steuerbote.doctype.vat_return_deviation.vat_return_deviation import VATReturnDeviation
		from steuerbote.steuerbote.doctype.vat_return_kennzahl.vat_return_kennzahl import VATReturnKennzahl
		from steuerbote.steuerbote.doctype.vat_return_unmapped_account.vat_return_unmapped_account import (
			VATReturnUnmappedAccount,
		)

		accounts_without_number: DF.Int
		amended_from: DF.Link | None
		attachments: DF.Check
		checks: DF.Table[VATReturnCheck]
		company: DF.Link
		deadline: DF.Date | None
		deviations: DF.Table[VATReturnDeviation]
		from_date: DF.Date | None
		input_tax: DF.Currency
		is_correction: DF.Check
		kennzahlen: DF.Table[VATReturnKennzahl]
		kz83: DF.Currency
		naming_series: DF.Literal["UStVA-.YYYY.-.#####"]
		no_sepa_mandate: DF.Check
		offset_requested: DF.Check
		other_tax: DF.Currency
		output_tax: DF.Currency
		period_code: DF.Data | None
		period_index: DF.Int
		period_label: DF.Data | None
		ready: DF.Check
		remarks: DF.SmallText | None
		rhythm: DF.Literal["monthly", "quarterly"]
		sondervorauszahlung: DF.Currency
		status: DF.Literal["Entwurf", "Berechnet", "Bereit", "Abgegeben", "Ersetzt"]
		supplementary_code: DF.Literal["", "1", "2", "3", "4"]
		to_date: DF.Date | None
		unmapped: DF.Table[VATReturnUnmappedAccount]
		year: DF.Int
	# end: auto-generated types

	def validate(self):
		if self._lacks_mandatory_values():
			return  # the mandatory check that follows names the missing fields
		self._require_catalogue()
		self._set_period()
		self._refuse_second_return()
		self._discard_calculation_of_another_period()
		self._set_final_amounts()

	def before_submit(self):
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the return before submitting it."))
		if not self.ready and not (self.remarks or "").strip():
			frappe.throw(
				_(
					"The return is not ready: a Verprobung deviates or a watched account has a balance. Explain in the remarks why it is filed nonetheless."
				)
			)
		self.status = FILED

	def on_submit(self):
		if self.is_correction:
			for name in self._other_filed_returns(status=FILED):
				frappe.get_doc("VAT Return", name).db_set("status", REPLACED)

	def on_cancel(self):
		latest = self._other_filed_returns()
		if latest and frappe.db.get_value("VAT Return", latest[0], "status") == REPLACED:
			frappe.get_doc("VAT Return", latest[0]).db_set("status", FILED)

	@frappe.whitelist(methods=["POST"])
	def calculate(self) -> None:
		"""Berechnen: compute the return from the general ledger of the period and save it."""
		if self.docstatus != 0:
			frappe.throw(_("Only a draft return can be calculated."))
		self._require_catalogue()
		year = cint(self.year)
		period, settings = self._set_period()
		catalogue = ustva.catalogue_for(year)
		overrides = _read_rows(bridge.overrides_of, self.kennzahlen, catalogue)
		lines = load_lines(self.company, period.start, period.end)
		try:
			result = ustva.calculate(
				lines,
				mapping_for(self.company, year),
				extra_values=bridge.sondervorauszahlung_values(
					period,
					settings.has_dauerfrist(year),
					bridge.to_amount(settings.sondervorauszahlung(year)),
				),
				tolerance=bridge.to_amount(settings.tolerance),
			)
		except ValueError as error:
			frappe.throw(str(error))
		self.set("kennzahlen", bridge.kennzahl_rows(result, catalogue, overrides))
		self.set("checks", bridge.check_rows(result))
		self.set("deviations", bridge.deviation_rows(result))
		self.set(
			"unmapped", bridge.unmapped_rows(result, lines, account_names(self.company, result.unmapped))
		)
		self.ready = int(result.ready)
		self.status = READY if result.ready else CALCULATED
		self.accounts_without_number = len(accounts_without_number(self.company))
		self.flags.calculating = True
		try:
			self.save()
		finally:
			self.flags.calculating = False

	def _lacks_mandatory_values(self) -> bool:
		return (
			not self.company
			or self.year is None
			or not self.rhythm
			or self.period_index is None
			or any(not row.kennzahl for row in self.kennzahlen)
		)

	def _require_catalogue(self) -> None:
		try:
			ustva.catalogue_for(cint(self.year))
		except ustva.UnknownYearError:
			frappe.throw(_("Steuerbote has no Kennzahlen for {0} yet.").format(self.year))

	def _set_period(self) -> tuple[ustva.Period, Document]:
		settings = settings_for(self.company)
		year = cint(self.year)
		period = self._chosen_period(year)
		prescribed = settings.rhythm_for(year, period.first_month)
		if prescribed is not period.rhythm:
			frappe.throw(
				_(
					"For month {0} of {1}, the VAT Return Settings of {2} prescribe filing {3}, not {4}."
				).format(period.first_month, year, self.company, _(prescribed.value), _(period.rhythm.value))
			)
		self.update(
			{
				"period_code": period.code,
				"period_label": period.label,
				"from_date": period.start,
				"to_date": period.end,
				"deadline": period.deadline(
					dauerfristverlaengerung=settings.has_dauerfrist(year), holidays=()
				),
			}
		)
		return period, settings

	def _chosen_period(self, year: int) -> ustva.Period:
		try:
			return ustva.Period(year, ustva.Rhythm(self.rhythm), cint(self.period_index))
		except ValueError:
			frappe.throw(
				_(
					"Filing {0}, there is no Voranmeldungszeitraum {1}: months run from 1 to 12, quarters from 1 to 4."
				).format(_(self.rhythm), self.period_index)
			)

	def _refuse_second_return(self) -> None:
		if self.is_correction:
			return
		filed = self._other_filed_returns()
		if filed:
			frappe.throw(
				_(
					"{0} of {1} is filed already as {2}. Mark this return as a corrected return (Kz 10)."
				).format(self.period_label, self.company, filed[0])
			)

	def _other_filed_returns(self, **filters) -> list[str]:
		"""The submitted returns for this company and period other than this one, the latest first."""
		return frappe.get_all(
			"VAT Return",
			filters={
				"company": self.company,
				"year": cint(self.year),
				"period_code": self.period_code,
				"docstatus": 1,
				"name": ["!=", self.name],
				**filters,
			},
			order_by="creation desc",
			pluck="name",
		)

	def _discard_calculation_of_another_period(self) -> None:
		before = self.get_doc_before_save()
		if not before or self.flags.calculating:
			return
		if any(str(before.get(field)) != str(self.get(field)) for field in PERIOD_FIELDS):
			for table in CALCULATED_TABLES:
				self.set(table, [])
			self.update({"ready": 0, "status": DRAFT, "accounts_without_number": 0})

	def _set_final_amounts(self) -> None:
		filing = _read_rows(bridge.filing, self.kennzahlen, cint(self.year))
		for row, values in zip(self.kennzahlen, filing.rows, strict=True):
			row.update(values)
		self.update(filing.totals)


def _read_rows(read, rows, *args):
	"""Call a reader of the Kennzahlen rows and turn a row it refuses into a message for the user."""
	try:
		return read(rows, *args)
	except bridge.RowError as error:
		if not error.kennzahl:
			frappe.throw(_("A row of the Kennzahlen table has no Kennzahl."))
		messages = {
			bridge.RowProblem.UNKNOWN: _("Kennzahl {0} is not on the form of this year."),
			bridge.RowProblem.DUPLICATE: _("Kennzahl {0} is listed twice."),
			bridge.RowProblem.NO_AMOUNT: _(
				"Kennzahl {0} takes no amount; it has a field of its own on the return."
			),
			bridge.RowProblem.COMPUTED: _("Kennzahl {0} is computed and cannot be overridden."),
			bridge.RowProblem.MISSING_REASON: _("The override of Kennzahl {0} needs a reason."),
		}
		frappe.throw(messages[error.problem].format(error.kennzahl))


def settings_for(company: str) -> Document:
	"""The company's VAT Return Settings: rhythm, Dauerfristverlängerung, Sondervorauszahlung, tolerance."""
	if not frappe.db.exists(SETTINGS_DOCTYPE, company):
		frappe.throw(
			_(
				"{0} has no VAT Return Settings. Create them for the company before its first VAT Return."
			).format(company)
		)
	return frappe.get_doc(SETTINGS_DOCTYPE, company)


def mapping_for(company: str, year: int) -> ustva.Mapping:
	"""The core Mapping of the company's VAT Return Mapping, validated against the form of the year."""
	if not frappe.db.exists(MAPPING_DOCTYPE, company):
		frappe.throw(
			_(
				"{0} has no VAT Return Mapping. Create one for the company, for example from the defaults of its chart, before calculating a VAT Return."
			).format(company)
		)
	return frappe.get_doc(MAPPING_DOCTYPE, company).to_mapping(year)
