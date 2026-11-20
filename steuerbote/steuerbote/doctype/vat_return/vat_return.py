"""VAT Return: the Umsatzsteuer-Voranmeldung of one company for one Voranmeldungszeitraum.

"Berechnen" (calculate) reads the period's general ledger through steuerbote.ledger, the company's VAT
Return Mapping and VAT Return Settings, and leaves every amount to the core in steuerbote.ustva; bridge.py
maps the results onto the tables. A company can switch between monthly and quarterly filing at the start of
a quarter, so a period number alone names a month or a quarter: the return carries its rhythm, which has to
be the one the settings prescribe for the first month of the period. An override replaces a computed amount
once it has a reason, and the totals and Kz 83 always follow the amounts as filed. "Berechnen" also fills the
Vorperiodenvergleich (build_comparison) and the hints (build_hints) of steuerbote.ustva.plausibility, which
inform and never change an amount or whether the return is ready. A period is filed once; every further
return for it is a corrected return (Kz 10), and filing one marks the returns before it as replaced. "XML für
Mein ELSTER" (make_import_file) writes the return as saved into the file for the import into Mein ELSTER
through steuerbote.elster.ustva_xml and attaches it to the return.

"Prüfen", "Testsenden" and "Senden" (transmit) run in a background job, as for every document that goes to
ELSTER through ERiC (elster_transmission/transmission.py): the job writes the same tree as the file for Mein
ELSTER with the Hersteller-ID for ERiC (nutzdaten) and hands it to steuerbote.eric, through the worker of an
installed runtime or the simulation; every run is recorded as an ELSTER Transmission. While it runs, the return
cannot change, so that the job files exactly what it sent. Only a successful real Senden submits the return,
which files it; "In Mein ELSTER abgegeben" and "Als außerhalb abgegeben vermerken" (mark_filed_outside) submit
it with a note instead. Submitting alone ("Buchen") files nothing and is refused, except for a return that
ELSTER accepted while its submission failed. A period counts as filed once a return of it is submitted or
another return of it was filed through Steuerbote, cancelled or not, and a return with a record of its filing
cannot be cancelled.
"""

import re
from decimal import Decimal

import frappe
from frappe import _
from frappe.core.doctype.file.utils import get_content_hash
from frappe.model.document import Document
from frappe.utils import cint, escape_html, fmt_money, getdate

from steuerbote import invoices, ustva
from steuerbote.elster import ustva_xml
from steuerbote.ledger import account_names, accounts_without_number, load_lines
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import (
	EXTERN,
	FILED_VIA,
	OTHER_WAY,
	SUCCEEDED,
	UNKNOWN,
)
from steuerbote.steuerbote.doctype.elster_transmission.transmission import Transmittable, filings
from steuerbote.steuerbote.doctype.vat_return import bridge
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors
from steuerbote.steuerbote.report.ustva_kennzahlen.comparison import Thresholds, year_before
from steuerbote.ustva import plausibility

DOCTYPE = "VAT Return"
SETTINGS_DOCTYPE = "VAT Return Settings"
MAPPING_DOCTYPE = "VAT Return Mapping"

DRAFT = "Entwurf"
CALCULATED = "Berechnet"
READY = "Bereit"
FILED = "Abgegeben"
REPLACED = "Ersetzt"

PERIOD_FIELDS = ("company", "year", "rhythm", "period_index")
CALCULATED_TABLES = ("kennzahlen", "checks", "deviations", "unmapped", "hints", "comparison")

# TransferTicketSType in headerbasis_datentypen.xsd of the ELSTER Basisschema.
TRANSFERTICKET = re.compile(r"[0-9a-km-z]{2}[0-9]{3}[0-9a-km-z]{27}")


class VATReturn(Transmittable, Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.vat_return_check.vat_return_check import VATReturnCheck
		from steuerbote.steuerbote.doctype.vat_return_comparison.vat_return_comparison import (
			VATReturnComparison,
		)
		from steuerbote.steuerbote.doctype.vat_return_deviation.vat_return_deviation import VATReturnDeviation
		from steuerbote.steuerbote.doctype.vat_return_hint.vat_return_hint import VATReturnHint
		from steuerbote.steuerbote.doctype.vat_return_kennzahl.vat_return_kennzahl import VATReturnKennzahl
		from steuerbote.steuerbote.doctype.vat_return_unmapped_account.vat_return_unmapped_account import (
			VATReturnUnmappedAccount,
		)

		accounts_without_number: DF.Int
		amended_from: DF.Link | None
		attachments: DF.Check
		checks: DF.Table[VATReturnCheck]
		company: DF.Link
		comparison: DF.Table[VATReturnComparison]
		deadline: DF.Date | None
		deviations: DF.Table[VATReturnDeviation]
		from_date: DF.Date | None
		hints: DF.Table[VATReturnHint]
		input_tax: DF.Currency
		is_correction: DF.Check
		kennzahlen: DF.Table[VATReturnKennzahl]
		kz500_begruendung: DF.SmallText | None
		kz83: DF.Currency
		naming_series: DF.Literal["UStVA-.{year}.-.#####"]
		no_sepa_mandate: DF.Check
		offset_requested: DF.Check
		other_tax: DF.Currency
		output_tax: DF.Currency
		period_code: DF.Data | None
		period_index: DF.Int
		period_label: DF.Data | None
		ready: DF.Check
		regelbesteuerung_from: DF.Date | None
		remarks: DF.SmallText | None
		rhythm: DF.Literal["monthly", "quarterly"]
		sondervorauszahlung: DF.Currency
		status: DF.Literal["Entwurf", "Berechnet", "Bereit", "Abgegeben", "Ersetzt"]
		supplementary_code: DF.Literal["", "1", "2", "3", "4"]
		to_date: DF.Date | None
		transmission_in_progress: DF.Check
		unmapped: DF.Table[VATReturnUnmappedAccount]
		year: DF.Int
	# end: auto-generated types

	def onload(self) -> None:
		self.set_onload("elster", self.elster_state())
		self.set_onload("elster_run", self.latest_run())

	def validate(self):
		self.refuse_changes_while_transmitting()
		if self._lacks_mandatory_values():
			return  # the mandatory check that follows names the missing fields
		self._require_catalogue()
		self._set_period()
		self._refuse_second_return()
		self._discard_calculation_of_another_period()
		self._set_final_amounts()
		self._check_supplementary_details()

	def before_submit(self):
		if not (self.flags.filing_transmission or self.flags.filed_outside or self.was_accepted()):
			frappe.throw(
				_(
					"A VAT Return is filed through Senden or by noting its filing in Mein ELSTER or outside Steuerbote, not by Buchen alone."
				)
			)
		self._check_fit_for_filing()
		self.status = FILED

	def before_cancel(self):
		if any(row.status == SUCCEEDED for row in self.filings()):
			frappe.throw(
				_(
					"{0} is filed with the Finanzamt and cannot be cancelled. A change goes to the Finanzamt as a corrected return (Kz 10)."
				).format(self.name)
			)

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
		"""Berechnen: compute the return from the general ledger of the period and save it, together with the
		Vorperiodenvergleich and the hints, which leave its amounts and whether it is ready as they are."""
		if self.docstatus != 0:
			frappe.throw(_("Only a draft return can be calculated."))
		self._require_catalogue()
		year = cint(self.year)
		period, settings = self._set_period()
		catalogue = ustva.catalogue_for(year)
		overrides = _read_rows(bridge.overrides_of, self.kennzahlen, catalogue)
		mapping = mapping_for(self.company, year)
		lines = load_lines(self.company, period.start, period.end)
		result = _calculated(lines, mapping, period, settings)
		self.set("kennzahlen", bridge.kennzahl_rows(result, catalogue, overrides))
		self.set("checks", bridge.check_rows(result))
		self.set("deviations", bridge.deviation_rows(result))
		self.set(
			"unmapped", bridge.unmapped_rows(result, lines, account_names(self.company, result.unmapped))
		)
		comparison = build_comparison(self, period, settings, mapping)
		self.set("comparison", bridge.comparison_rows(comparison))
		self.set("hints", bridge.hint_rows(build_hints(self, period, mapping, result, comparison)))
		self.ready = int(result.ready)
		self.status = READY if result.ready else CALCULATED
		self.accounts_without_number = len(accounts_without_number(self.company))
		self.flags.calculating = True
		try:
			self.save()
		finally:
			self.flags.calculating = False

	@frappe.whitelist(methods=["POST"])
	def make_import_file(self) -> str:
		"""XML für Mein ELSTER: the return as saved, as a file to import into the form, attached privately.

		The file is made for a return that could be filed, calculated and ready or explained in the remarks,
		and for the return filed for the period. Returns the address of the file.
		"""
		saved = frappe.get_doc(self.doctype, self.name)
		saved._require_import_file()
		with xml_errors(_("XML for Mein ELSTER")):
			period = saved._chosen_period(cint(saved.year))
			voranmeldung = bridge.voranmeldung(saved, period, saved._reported_before())
			filer = bridge.filer(settings_for(saved.company))
			content = ustva_xml.to_import_file(filer, voranmeldung, getdate())
		return saved._attach(ustva_xml.import_file_name(voranmeldung), content)

	@frappe.whitelist(methods=["POST"])
	def mark_filed_outside(
		self,
		remarks: str | None = None,
		filed_via: str = OTHER_WAY,
		transferticket: str | None = None,
		filed_on: str | None = None,
	) -> str:
		"""In Mein ELSTER abgegeben, or Als außerhalb abgegeben vermerken: the return went to the Finanzamt
		another way, such as the file for Mein ELSTER or the Steuerberatung. Submits the return, records how
		and when, with the Transferticket if there is one, and returns the ELSTER Transmission's name."""
		self.check_permission("submit")
		note = (remarks or "").strip()
		ticket = (transferticket or "").strip()
		if filed_via not in FILED_VIA:
			frappe.throw(_("Steuerbote knows no way of filing {0}.").format(escape_html(str(filed_via))))
		if filed_via == OTHER_WAY and not note:
			frappe.throw(_("Note how and when the return was filed."))
		if ticket and not TRANSFERTICKET.fullmatch(ticket):
			frappe.throw(
				_(
					"{0} is no Transferticket: it has 32 characters, as the protocol of ELSTER shows it."
				).format(escape_html(ticket))
			)
		filed_date = getdate(filed_on) if filed_on else None
		if filed_date and filed_date > getdate():
			frappe.throw(_("A return cannot be filed in the future."))
		self.lock_for_transmission()
		if self.docstatus != 0:
			frappe.throw(_("Only a draft return can be marked as filed."))
		accepted = [row for row in self.filings() if row.status == SUCCEEDED]
		if accepted:
			frappe.throw(
				_(
					"ELSTER accepted {0} with Transferticket {1}, so it was not filed outside Steuerbote: submit it with Buchen."
				).format(self.name, accepted[0].transferticket)
			)
		self._refuse_second_filing()
		self.flags.filed_outside = True
		self.submit()
		return self.new_transmission(
			EXTERN,
			simulated=False,
			status=SUCCEEDED,
			remarks=note or None,
			filed_via=filed_via,
			transferticket=ticket or None,
			filed_on=filed_date,
		).name

	def _check_fit_for_filing(self) -> None:
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the return before submitting it."))
		if not self.ready and not (self.remarks or "").strip():
			frappe.throw(
				_(
					"The return is not ready: a Verprobung deviates or a watched account has a balance. Explain in the remarks why it is filed nonetheless."
				)
			)

	def check_transmittable(self) -> None:
		if self.docstatus != 0:
			frappe.throw(
				_(
					"Only a draft return can be transmitted. A filed return is corrected by a corrected return (Kz 10)."
				)
			)
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the return before transmitting it."))

	def check_can_be_sent(self) -> None:
		"""Senden files the return, once: it needs the return fit for filing and no earlier filing."""
		self._check_fit_for_filing()
		sent = self.filings()
		if sent and sent[0].status == UNKNOWN:
			frappe.throw(
				_(
					"Whether {0} reached ELSTER is unknown. Check in Mein ELSTER whether the return arrived: if it did, mark it as filed outside; if not, a System Manager deletes {0}, then the return can be sent again."
				).format(sent[0].name)
			)
		if sent:
			frappe.throw(
				_(
					"This return was transmitted already with Transferticket {0}. A change goes to the Finanzamt as a corrected return (Kz 10)."
				).format(sent[0].transferticket)
			)
		self._refuse_second_filing()

	def _refuse_second_filing(self) -> None:
		"""A period is filed once: after a return of it is submitted, or sent through Steuerbote even if it
		was cancelled later, every other return of it is a corrected return (Kz 10)."""
		self._refuse_second_return()
		if self.is_correction:
			return
		others = frappe.get_all(
			DOCTYPE,
			filters={
				"company": self.company,
				"year": cint(self.year),
				"period_code": self.period_code,
				"name": ["!=", self.name],
			},
			pluck="name",
		)
		sent = filings(DOCTYPE, others)
		if sent:
			frappe.throw(
				_(
					"{0} of {1} was transmitted already as {2}. Mark this return as a corrected return (Kz 10)."
				).format(self.period_label, self.company, sent[0].document)
			)

	def nutzdaten(self, hersteller_id: str) -> str:
		"""The Nutzdaten for ERiC: the tree of the file for Mein ELSTER, with the Hersteller-ID in Kz 09."""
		with xml_errors(_("ELSTER Transmission")):
			period = self._chosen_period(cint(self.year))
			voranmeldung = bridge.voranmeldung(self, period, self._reported_before())
			filer = bridge.filer(settings_for(self.company))
			return ustva_xml.to_nutzdaten(filer, voranmeldung, getdate(), hersteller_id)

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

	def _check_supplementary_details(self) -> None:
		"""Kz 500 and its Begründung go together, the Begründung on one line ELSTER takes, and the date of the
		switch to the Regelbesteuerung in Kz 70 lies in the year of the return."""
		with xml_errors(_("VAT Return")):
			ustva_xml.supplementary_details(self.supplementary_code, self.kz500_begruendung)
			ustva_xml.regelbesteuerung_details(bridge.to_date(self.regelbesteuerung_from), cint(self.year))

	def _require_import_file(self) -> None:
		if self.docstatus == 1 and self.status == FILED:
			return
		if self.docstatus != 0:
			frappe.throw(
				_(
					"A replaced or cancelled return makes no file for Mein ELSTER; make it from the return filed."
				)
			)
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the return before making the file for Mein ELSTER."))
		self._refuse_second_filing()
		if not self.ready and not (self.remarks or "").strip():
			frappe.throw(
				_(
					"The return is not ready: a Verprobung deviates or a watched account has a balance. Explain in the remarks why it is filed nonetheless."
				)
			)

	def _reported_before(self) -> frozenset[str]:
		"""What the other filed returns of the period reported, which a corrected return writes as zero."""
		if not self.is_correction:
			return frozenset()
		return frozenset().union(
			*(
				bridge.reported(frappe.get_doc("VAT Return", name).kennzahlen)
				for name in self._other_filed_returns()
			)
		)

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


def _calculated(
	lines: list[ustva.LedgerLine], mapping: ustva.Mapping, period: ustva.Period, settings: Document
) -> ustva.UstvaResult:
	"""The core's result for a period, with Kz 39 in the last period of a year with Dauerfristverlängerung."""
	try:
		return ustva.calculate(
			lines,
			mapping,
			extra_values=bridge.sondervorauszahlung_values(
				period,
				settings.has_dauerfrist(period.year),
				bridge.to_amount(settings.sondervorauszahlung(period.year)),
			),
			tolerance=bridge.to_amount(settings.tolerance),
		)
	except ValueError as error:
		frappe.throw(str(error))


def build_comparison(
	doc: Document, period: ustva.Period, settings: Document, mapping: ustva.Mapping
) -> plausibility.Comparison:
	"""Vorperiodenvergleich: the amounts the return files against the previous period of its rhythm and
	against the same period a year earlier. A Kennzahl is flagged by the rule the report UStVA Kennzahlen
	filters its deviations with, on the thresholds of the settings.

	The earlier amounts come from the ledger, through the same query and the company's mapping validated
	against the form of their year, and never from earlier VAT Returns: the ledger is the single source of
	every Kennzahl, and the comparison has to work before any earlier return exists. A year without a catalogue
	of Kennzahlen, or with a form the mapping does not fit, leaves the amounts of its period empty and costs no
	query.
	"""
	thresholds = Thresholds.of(
		settings.get("comparison_threshold_percent"), settings.get("comparison_threshold_amount")
	)
	return plausibility.compare(
		_read_rows(bridge.final_amounts, doc.kennzahlen, period.year),
		_earlier_period(doc.company, period.previous(), settings, mapping),
		_earlier_period(doc.company, year_before(period), settings, mapping),
		mapping.catalogue,
		thresholds.exceeded,
	)


def _earlier_period(
	company: str, period: ustva.Period, settings: Document, mapping: ustva.Mapping
) -> plausibility.EarlierPeriod:
	try:
		mapping_of_the_year = mapping.for_year(period.year)
	except ustva.UnknownYearError:
		return plausibility.EarlierPeriod(period, None, plausibility.Code.NO_CATALOGUE)
	except ustva.MappingError:
		return plausibility.EarlierPeriod(period, None, plausibility.Code.MAPPING_UNFIT)
	result = _calculated(load_lines(company, period.start, period.end), mapping_of_the_year, period, settings)
	return plausibility.EarlierPeriod(
		period, {number: value.reported for number, value in result.values.items()}
	)


def build_hints(
	doc: Document,
	period: ustva.Period,
	mapping: ustva.Mapping,
	result: ustva.UstvaResult,
	comparison: plausibility.Comparison,
) -> tuple[plausibility.Hint, ...]:
	"""Hinweise: the invoices of the period, their reconciliation with the ledger and the Vorperiodenvergleich.

	A hint informs and never holds the return; whether it is ready follows the Verprobung and the watched
	accounts alone.
	"""
	lines = invoices.load_lines(
		doc.company,
		period.start,
		period.end,
		plausibility.sales_accounts(mapping),
		plausibility.purchase_accounts(mapping),
	)
	ledger = {number: value.amount for number, value in result.values.items()}
	currency = frappe.get_cached_value("Company", doc.company, "default_currency")
	return plausibility.hints(comparison, lines, ledger, mapping, SiteFigures(currency))


class SiteFigures:
	"""The figures of a hint in the number format of the site, amounts in the company's currency."""

	def __init__(self, currency: str) -> None:
		self.currency = currency

	def money(self, amount: Decimal) -> str:
		return fmt_money(amount, currency=self.currency)

	def percent(self, value: Decimal) -> str:
		return f"{fmt_money(value, precision=1)} %"
