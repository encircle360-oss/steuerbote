"""VAT Return: the Umsatzsteuer-Voranmeldung of one company for one Voranmeldungszeitraum.

"Berechnen" (calculate) reads the period's general ledger through steuerbote.ledger, the company's VAT
Return Mapping and VAT Return Settings, and leaves every amount to the core in steuerbote.ustva; bridge.py
maps the results onto the tables. A company can switch between monthly and quarterly filing at the start of
a quarter, so a period number alone names a month or a quarter: the return carries its rhythm, which has to
be the one the settings prescribe for the first month of the period. An override replaces a computed amount
once it has a reason, and the totals and Kz 83 always follow the amounts as filed. Frappe keeps no read-only
field from a save through its API, so a save keeps what Berechnen stored and takes only what the form lets the
user change, a new return starts as a draft, and before the return is transmitted, made into a file or filed, its
amounts are computed again from the stored Kennzahlen. "Berechnen" also fills the
Vorperiodenvergleich (build_comparison) and the hints (build_hints) of steuerbote.ustva.plausibility, which never
change an amount; an error among them holds the return back from „Bereit“ (bridge.ready_of): a customer without a valid
USt-IdNr. behind Kz 41, 42 or 21, which the Zusammenfassende Meldung holds the same way, and an override whose ledger
amount changed since it was made (bridge.stale_override_hints). An override keeps that amount (bridge.override_bases),
from the stored return and never from the rows a save sends. The reconciliation with the reports Sales
Register and Purchase Register (build_reconciliation, steuerbote.ustva.registers): a difference there needs an
explanation in its row, or the remarks, before the return is transmitted, made into a file or filed, as a return
that is not ready needs the remarks. A return of a year whose forms are provisional (steuerbote/ustva/years.py) is not
ready either and says so in Vorläufige Vordrucke, as the Körperschaftsteuererklärung does. A period is filed once; every further return for it is a corrected return
(Kz 10), and filing one marks the returns before it as replaced. "XML für
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
cannot be cancelled. A draft that ELSTER accepted, or whose Senden has an unknown outcome, keeps all but its
remarks, since the Finanzamt has it, or may have it, as it was sent.

"USt-IdNrn. prüfen" (confirm_vat_ids) asks the BZSt about the USt-IdNr. of each customer behind Kz 41, 42 and 21 of
the period, in a background job as at the Zusammenfassende Meldung (vat_id_confirmation/confirming.py), and the
hints name each number whose latest confirmation is missing, out of date or found it invalid (vat_id_hints). The job
gives these hints anew when it has finished; the return does not change while it runs.
"""

import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal

import frappe
from frappe import _
from frappe.core.doctype.file.utils import get_content_hash
from frappe.model.document import Document
from frappe.utils import cint, escape_html, fmt_money, formatdate, getdate

from steuerbote import invoices, prior_filings, ustva, zm_sources
from steuerbote.elster import ustva_xml
from steuerbote.eric import datenart as eric_datenart
from steuerbote.ledger import (
	account_labels,
	account_names,
	accounts_without_number,
	closing_balances,
	load_lines,
)
from steuerbote.registers import register_lines
from steuerbote.setup.start import before_start
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import (
	EXTERN,
	FILED_VIA,
	OTHER_WAY,
	SUCCEEDED,
	UNKNOWN,
)
from steuerbote.steuerbote.doctype.elster_transmission.transmission import Transmittable, filings
from steuerbote.steuerbote.doctype.recapitulative_statement import bridge as zm_bridge
from steuerbote.steuerbote.doctype.vat_id_confirmation import confirming, vat_id_confirmation
from steuerbote.steuerbote.doctype.vat_id_confirmation.confirming import Confirming
from steuerbote.steuerbote.doctype.vat_return import bridge, late
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors
from steuerbote.steuerbote.report.ustva_kennzahlen.comparison import Thresholds, year_before
from steuerbote.suppliers import load_vouchers
from steuerbote.tax_templates import template_accounts
from steuerbote.ustva import carried, plausibility, registers, tax_templates
from steuerbote.ustva.assignment import changes
from steuerbote.ustva.defaults import TIMING_ACCOUNTS, deliberately_without_kennzahl
from steuerbote.vat_periods import VatLedger, filed_amounts
from steuerbote.vatid import Details, UrllibFetch
from steuerbote.zm.lines import VoucherAmount

DOCTYPE = "VAT Return"
SETTINGS_DOCTYPE = "VAT Return Settings"
MAPPING_DOCTYPE = "VAT Return Mapping"

DRAFT = "Entwurf"
CALCULATED = "Berechnet"
READY = "Bereit"
FILED = "Abgegeben"
REPLACED = "Ersetzt"

PERIOD_FIELDS = ("company", "year", "rhythm", "period_index")
# What Berechnen finds besides the Kennzahlen: the Verprobung, the watched accounts, the hints, the comparison and
# what changed after the filing of earlier periods.
FINDINGS = ("checks", "deviations", "unmapped", "hints", "comparison", "late_changes")
# The reconciliation with the registers, which Berechnen fills and whose explanations a save takes.
RECONCILIATION = "register_reconciliation"
CALCULATED_TABLES = ("kennzahlen", *FINDINGS, RECONCILIATION)
CALCULATED_FIELDS = (
	"status",
	"ready",
	"accounts_without_number",
	"period_basis",
	"late_treatment",
	"statutory_tax",
)

# TransferTicketSType in headerbasis_datentypen.xsd of the ELSTER Basisschema.
TRANSFERTICKET = re.compile(r"[0-9a-km-z]{2}[0-9]{3}[0-9a-km-z]{27}")
CONFIRMATION_JOB = "steuerbote.steuerbote.doctype.vat_return.vat_return.run_confirmation"


class VATReturn(Confirming, Transmittable, Document):
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
		from steuerbote.steuerbote.doctype.vat_return_late_change.vat_return_late_change import (
			VATReturnLateChange,
		)
		from steuerbote.steuerbote.doctype.vat_return_register_reconciliation.vat_return_register_reconciliation import (
			VATReturnRegisterReconciliation,
		)
		from steuerbote.steuerbote.doctype.vat_return_unmapped_account.vat_return_unmapped_account import (
			VATReturnUnmappedAccount,
		)

		accounts_without_number: DF.Int
		amended_from: DF.Link | None
		attachments: DF.Check
		checks: DF.Table[VATReturnCheck]
		company: DF.Link
		comparison: DF.Table[VATReturnComparison]
		confirmation_in_progress: DF.Check
		deadline: DF.Date | None
		deviations: DF.Table[VATReturnDeviation]
		from_date: DF.Date | None
		hints: DF.Table[VATReturnHint]
		input_tax: DF.Currency
		is_correction: DF.Check
		kennzahlen: DF.Table[VATReturnKennzahl]
		kz500_begruendung: DF.SmallText | None
		kz83: DF.Currency
		late_changes: DF.Table[VATReturnLateChange]
		late_treatment: DF.Literal["", "Corrected Return", "Current Period"]
		naming_series: DF.Literal["UStVA-.{year}.-.#####"]
		no_sepa_mandate: DF.Check
		offset_requested: DF.Check
		other_tax: DF.Currency
		output_tax: DF.Currency
		period_code: DF.Data | None
		period_basis: DF.Literal["", "By Service Date", "By Posting Date"]
		period_index: DF.Int
		period_label: DF.Data | None
		provisional: DF.Check
		ready: DF.Check
		register_reconciliation: DF.Table[VATReturnRegisterReconciliation]
		regelbesteuerung_from: DF.Date | None
		remarks: DF.SmallText | None
		rhythm: DF.Literal["monthly", "quarterly"]
		sondervorauszahlung: DF.Currency
		statutory_tax: DF.Literal["", "From the Base in Full Euros", "As Booked"]
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
		self.set_onload("confirmation", self.confirmation_state())
		if self.docstatus == 1 and self.status == FILED:
			self.set_onload("changes_since_filing", self.changes_since_filing())

	def before_insert(self) -> None:
		"""A new return starts as a draft that Berechnen has not read, whatever it was made with: its Kennzahlen keep
		their overrides without a computed amount, and nothing else of a calculation stays."""
		for table in (*FINDINGS, RECONCILIATION):
			self.set(table, [])
		for row in self.kennzahlen:
			row.update({"amount": 0, "reported": 0})
		self.update(
			{
				"status": DRAFT,
				"ready": 0,
				"accounts_without_number": 0,
				"period_basis": "",
				"late_treatment": "",
				"statutory_tax": "",
			}
		)

	def validate(self):
		self.refuse_changes_while_transmitting()
		self.refuse_changes_while_confirming()
		self.refuse_changes_after_sending()
		if self._lacks_mandatory_values():
			return  # the mandatory check that follows names the missing fields
		self._refuse_a_period_before_the_start()
		self._require_catalogue()
		self.provisional = int(bridge.provisional_forms(cint(self.year)) is not None)
		self._set_period()
		self._refuse_second_return()
		self._keep_the_calculation()
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
		self._require_amounts_as_stored(self.get_doc_before_save() or self)
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
		self.refuse_if_sent()
		self.refuse_changes_while_confirming()
		self._require_catalogue()
		year = cint(self.year)
		period, settings = self._set_period()
		catalogue = ustva.catalogue_for(year)
		self._take_bases(self._stored_kennzahlen())
		overrides = _read_rows(bridge.overrides_of, self.kennzahlen, catalogue)
		mapping = mapping_for(self.company, year)
		ledger = VatLedger.for_period(self.company, period)
		lines = ledger.lines(period)
		result, release_hints = released(
			self.company, _calculated(lines, mapping, period, settings), lines, mapping, period
		)
		self.statutory_tax = statutory_tax_of(settings).value
		self.set("kennzahlen", bridge.kennzahl_rows(result, catalogue, overrides))
		self.set("checks", bridge.check_rows(result))
		self.set("deviations", bridge.deviation_rows(result))
		self.set(
			"unmapped", bridge.unmapped_rows(result, lines, account_names(self.company, result.unmapped))
		)
		comparison = build_comparison(self, period, settings, mapping, ledger)
		self.set("comparison", bridge.comparison_rows(comparison))
		self.set("late_changes", late_change_rows(ledger, period, settings, mapping))
		self.update({"period_basis": ledger.basis.value, "late_treatment": ledger.treatment.value})
		reconciliation = build_reconciliation(
			self.company, period, mapping, load_lines(self.company, period.start, period.end)
		)
		numbers = [row.account_number for row in reconciliation if row.account_number]
		self.set(
			RECONCILIATION,
			bridge.reconciliation_rows(
				reconciliation,
				catalogue,
				account_names(self.company, numbers),
				account_labels(self.company, numbers),
				self.get(RECONCILIATION),
			),
		)
		hints = build_hints(self, period, mapping, result, comparison, reconciliation, sales_invoices(lines))
		stale = bridge.stale_override_hints(self.kennzahlen, _figures(self.company))
		self.set("hints", bridge.hint_rows(plausibility.merged(stale, (*hints, *release_hints))))
		self._set_ready()
		self.accounts_without_number = len(accounts_without_number(self.company))
		self.flags.calculating = True
		try:
			self.save()
		finally:
			self.flags.calculating = False

	def changes_since_filing(self) -> list[dict] | None:
		"""For the form of a filed return: the bookings made after the filing of its period, where they are
		reported, and the Kennzahlen whose ledger amounts changed since; None when the ledger cannot be read."""
		try:
			period = self._chosen_period(cint(self.year))
			settings = settings_for(self.company)
			mapping = mapping_for(self.company, period.year)
			ledger = VatLedger(self.company, date(period.year, 1, 1), period.end)
			rows = [
				*late.filed_rows(ledger.late(), period),
				*_change_rows(ledger, period, settings, mapping),
			]
		except frappe.ValidationError:
			return None
		return [_late_row(row) for row in rows]

	@frappe.whitelist(methods=["POST"])
	def make_correction(self) -> str:
		"""Berichtigung anlegen: a draft corrected return (Kz 10) of the period of this filed return, or the draft
		correction that exists already; returns its name."""
		self.check_permission("read")
		frappe.has_permission(DOCTYPE, "create", throw=True)
		if self.docstatus != 1 or self.status != FILED:
			frappe.throw(_("Only the filed return of a period is corrected."))
		period = {field: self.get(field) for field in ("company", "year", "rhythm", "period_index")}
		draft = frappe.db.get_value(DOCTYPE, {**period, "docstatus": 0, "is_correction": 1}, "name")
		if draft:
			return draft
		return frappe.get_doc({"doctype": DOCTYPE, **period, "is_correction": 1}).insert().name

	@frappe.whitelist(methods=["POST"])
	def confirm_vat_ids(self) -> int:
		"""USt-IdNrn. prüfen: ask about the USt-IdNr. of each customer behind Kz 41, 42 and 21 of the period, in a
		background job; returns how many numbers the job asks about."""
		self.check_permission("write")
		self.lock_for_confirmation()
		if self.docstatus != 0:
			frappe.throw(_("Only the USt-IdNrn. of a draft return are confirmed."))
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the return before confirming its USt-IdNrn."))
		if cint(self.transmission_in_progress):
			frappe.throw(_("A transmission of {0} is running. Wait for its result.").format(self.name))
		self.refuse_if_sent()
		return self.start_confirmation(
			self.numbers_to_confirm(),
			CONFIRMATION_JOB,
			_("No customer behind Kz 41, 42 or 21 of the period has a USt-IdNr. to confirm."),
		)

	def numbers_to_confirm(self) -> list[str]:
		"""The USt-IdNrn. of the customers behind Kz 41, 42 and 21 of the period that the BZSt can confirm, each once."""
		return plausibility.confirmable(self._vat_ids().amounts)

	def details_for(self, vat_id: str) -> Details | None:
		"""Name and address of the customer of the first voucher of the number that names one, as the ZM reads them."""
		return zm_sources.customer_details(zm_bridge.customer_of(self._vat_ids().vouchers, vat_id))

	def take_in_confirmations(self) -> None:
		"""The hints on the USt-IdNrn. follow the confirmations the job stored; every other hint stays as Berechnen
		found it."""
		period = self._chosen_period(cint(self.year))
		hints = vat_id_hints(self.company, period, self._vat_ids().amounts)
		self.set("hints", bridge.replaced_hints(self.hints, hints, plausibility.VAT_ID_CODES))
		self.flags.confirming = True
		self.save()

	def _set_ready(self) -> None:
		"""Bereit or Berechnet, from the Verprobung, the watched accounts, the errors among the hints and the forms of
		the year, as the return stores them."""
		provisional = bridge.provisional_forms(cint(self.year)) is not None
		self.ready = int(bridge.ready_of(self.checks, self.unmapped, self.hints, provisional))
		self.status = READY if self.ready else CALCULATED

	def _stored_kennzahlen(self) -> list[Document]:
		"""The Kennzahlen of the return as the database holds them, none before its first save."""
		if self.is_new() or not frappe.db.exists(DOCTYPE, self.name):
			return []
		return frappe.get_doc(DOCTYPE, self.name).kennzahlen

	def _take_bases(self, stored: Iterable[Document]) -> None:
		"""Give each override the ledger amount it was made against (bridge.override_bases); a Kennzahl the stored return
		did not hold has no ledger amount yet but the one Berechnen finds."""
		for row, basis in zip(self.kennzahlen, bridge.override_bases(stored, self.kennzahlen), strict=True):
			row.override_basis = basis

	def _vat_ids(self) -> PeriodVatIds:
		"""The vouchers behind Kz 41, 42 and 21 of the period with their customers, read once for the document."""
		if getattr(self, "_period_vat_ids", None) is None:
			year = cint(self.year)
			self._period_vat_ids = period_vat_ids(
				self.company, self._chosen_period(year), mapping_for(self.company, year)
			)
		return self._period_vat_ids

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
		self._warn_filed_before_the_end(filed_date or getdate())
		return self.new_transmission(
			EXTERN,
			simulated=False,
			status=SUCCEEDED,
			remarks=note or None,
			filed_via=filed_via,
			transferticket=ticket or None,
			filed_on=filed_date,
		).name

	def _warn_filed_before_the_end(self, filed_on: date) -> None:
		"""A return noted as filed before its period has ended may miss bookings made later in it, which a corrected
		return then has to report (§ 18 Absatz 1 UStG: the Voranmeldung follows the end of the period)."""
		if filed_on <= getdate(self.to_date):
			frappe.msgprint(
				_(
					"{0} was noted as filed on {1}, before the period ends on {2}. A booking made for it later needs a corrected return (Kz 10)."
				).format(self.period_label, formatdate(filed_on), formatdate(self.to_date)),
				indicator="orange",
			)

	def _check_fit_for_filing(self) -> None:
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the return before submitting it."))
		if not self.ready and not (self.remarks or "").strip():
			frappe.throw(self._not_ready())
		self._require_explained_differences()

	def _not_ready(self) -> str:
		"""Why a return that is not ready is filed with remarks only: the forms of a provisional year, or else the
		Verprobung and the watched accounts."""
		forms = bridge.provisional_forms(cint(self.year))
		if forms is not None:
			return _(
				"Steuerbote has the forms of {0} provisionally from the documentation of {1} and form USt 1 A {2}: until ERiC and the BMF publish those of {0}, the return is not ready. Explain in the remarks why it is filed nonetheless."
			).format(cint(self.year), forms["documentation"], forms["form_year"])
		return _(
			"The return is not ready: a Verprobung deviates, a watched account has a balance, or an error among the hints holds it, such as a customer without a valid USt-IdNr. or an override whose ledger amount changed. Explain in the remarks why it is filed nonetheless."
		)

	def provisional_forms(self) -> dict | None:
		"""The documentation of ERiC and the year of the form that a provisional year takes, for the mark under the title
		of the print format „Umsatzsteuer-Voranmeldung“; None for a final year."""
		return bridge.provisional_forms(cint(self.year))

	def _require_explained_differences(self) -> None:
		"""Eine Abweichung muss erklärt sein (docs/roadmap.md, Grundsätze): each difference to the registers needs an
		explanation in its row before the return is transmitted, made into a file or filed, unless the remarks explain
		why it is filed nonetheless, as they do for a return that is not ready."""
		if (self.remarks or "").strip():
			return
		subjects = bridge.unexplained(self.get(RECONCILIATION))
		if subjects:
			frappe.throw(
				_(
					"The reconciliation with the registers shows a difference without an explanation: {0}. Explain it in its row, or in the remarks why the return is filed nonetheless."
				).format(escape_html("; ".join(subjects)))
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
		self.refuse_while_confirming()
		self._require_amounts_as_stored(self)
		self._require_explained_differences()

	def check_can_be_sent(self) -> None:
		"""Senden files the return, once: it needs the return fit for filing and no earlier filing."""
		self._check_fit_for_filing()
		self._refuse_sent_return()
		self._refuse_second_filing()

	def _refuse_sent_return(self) -> None:
		"""The Finanzamt has a return whose Senden through Steuerbote ELSTER accepted, or may have it when the
		outcome is unknown: it is neither sent again nor made into the file for Mein ELSTER."""
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

	def datenart(self) -> eric_datenart.Datenart:
		"""The Datenart UStVA of the year of the return."""
		return eric_datenart.ustva(cint(self.year))

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

	def _refuse_a_period_before_the_start(self) -> None:
		"""A period that begins before the start of the books in Steuerbote was filed outside it, and the ledger holds
		only the opening balances of that time (steuerbote/setup/start.py): a return computed from it would file
		nothing, and as a corrected return replace what the Finanzamt has."""
		books_start = prior_filings.books_start(self.company)
		period = self._chosen_period(cint(self.year))
		if before_start(period.start, books_start):
			frappe.throw(
				_(
					"{0} begins before the start of the books in Steuerbote on {1}: its Voranmeldung was filed outside Steuerbote, and the ledger holds only the opening balances of that time. Enter it as a VAT Return Prior Filing; a corrected return of it goes where the books of that time are kept."
				).format(period.label, formatdate(books_start))
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

	def _keep_the_calculation(self) -> None:
		"""Frappe keeps no read-only field from a save through its API, so a save keeps what Berechnen stored and
		takes only what the form lets the user change: the overrides with their reasons, the further details and the
		remarks. Another company or period discards the calculation instead. A new return is a draft (before_insert),
		so a calculated one was saved before. The job of USt-IdNrn. prüfen alone gives the hints anew
		(take_in_confirmations)."""
		before = self.get_doc_before_save()
		if before is None or self.flags.calculating:
			return
		if any(str(before.get(field)) != str(self.get(field)) for field in PERIOD_FIELDS):
			for table in CALCULATED_TABLES:
				self.set(table, [])
			self.update({"ready": 0, "status": DRAFT, "accounts_without_number": 0})
			return
		computed = _read_rows(bridge.restored, before.kennzahlen, self.kennzahlen)
		self._take_bases(before.kennzahlen)
		for row, values in zip(self.kennzahlen, computed, strict=True):
			row.update(values)
			if row.override_basis is None:
				row.override_basis = row.amount
		for table in FINDINGS:
			if not (table == "hints" and self.flags.confirming):
				self.set(table, [row.as_dict() for row in before.get(table)])
		stale = bridge.stale_override_hints(self.kennzahlen, _figures(self.company))
		code = plausibility.Code.OVERRIDE_STALE
		if [row.text for row in self.hints if row.code == code] != [hint.text for hint in stale]:
			self.set("hints", bridge.replaced_hints(self.hints, stale, frozenset({code})))
		self.set(
			RECONCILIATION,
			bridge.explanations_kept(
				[row.as_dict() for row in before.get(RECONCILIATION)], self.get(RECONCILIATION)
			),
		)
		self.update({field: before.get(field) for field in CALCULATED_FIELDS})
		if self.status in (CALCULATED, READY):
			self._set_ready()

	def statutory_tax_of_the_return(self) -> ustva.StatutoryTax:
		"""The setting „Steuer zu Umsätzen mit festem Steuersatz“ the return was calculated with."""
		return bridge.statutory_tax_of(self.statutory_tax)

	def statutory_taxes(self) -> dict[str, float]:
		"""For the print format „Umsatzsteuer-Voranmeldung“: the tax as booked of each base at a statutory rate that the
		return files; a base without one prints the tax of the form, the rate times the base in full euros."""
		taxes = _read_rows(
			bridge.filed_taxes,
			self.kennzahlen,
			ustva.catalogue_for(cint(self.year)),
			self.statutory_tax_of_the_return(),
		)
		return {number: float(tax) for number, tax in taxes.items()}

	def _set_final_amounts(self) -> None:
		filing = _read_rows(
			bridge.filing, self.kennzahlen, cint(self.year), self.statutory_tax_of_the_return()
		)
		for row, values in zip(self.kennzahlen, filing.rows, strict=True):
			row.update(values)
		self.update(filing.totals)

	def _require_amounts_as_stored(self, stored: Document) -> None:
		"""A filing carries the amounts the return holds, which every save sets from its Kennzahlen: computed again
		from the rows, they are the amounts ``stored`` holds, or nothing is filed."""
		if not _read_rows(
			bridge.amounts_kept,
			self.kennzahlen,
			stored,
			cint(self.year),
			self.statutory_tax_of_the_return(),
		):
			frappe.throw(
				_(
					"The amounts of {0} do not agree with its Kennzahlen as stored. Reload the return, and calculate it again if they still do not agree."
				).format(self.name)
			)

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
		self._refuse_sent_return()
		self._refuse_second_filing()
		if not self.ready and not (self.remarks or "").strip():
			frappe.throw(self._not_ready())
		self._require_explained_differences()
		self._require_amounts_as_stored(self)

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
			bridge.RowProblem.REMOVED: _(
				"Kennzahl {0} comes from the general ledger and stays on the return; an override with a reason files another amount."
			),
		}
		frappe.throw(messages[error.problem].format(error.kennzahl))


def settings_for(company: str) -> Document:
	"""The company's VAT Return Settings: rhythm, Dauerfristverlängerung, Sondervorauszahlung, tolerance, the tax of the
	bases at a statutory rate."""
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


def statutory_tax_of(settings: Document) -> ustva.StatutoryTax:
	"""The setting „Steuer zu Umsätzen mit festem Steuersatz“ of the VAT Return Settings; settings saved before it
	existed take the tax of the form until the patch fills it."""
	return bridge.statutory_tax_of(settings.get("statutory_tax"))


def _calculated(
	lines: list[ustva.LedgerLine], mapping: ustva.Mapping, period: ustva.Period, settings: Document
) -> ustva.UstvaResult:
	"""The core's result for a period, with Kz 39 in the last period of a year with Dauerfristverlängerung, with
	the suppliers of the vouchers of sections C and D (steuerbote.suppliers) and the tax of the bases at a statutory
	rate as the settings choose it."""
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
			vouchers=load_vouchers(settings.company, lines, mapping),
			statutory_tax=statutory_tax_of(settings),
		)
	except ValueError as error:
		frappe.throw(str(error))


def released(
	company: str,
	result: ustva.UstvaResult,
	lines: list[ustva.LedgerLine],
	mapping: ustva.Mapping,
	period: ustva.Period,
) -> tuple[ustva.UstvaResult, list[plausibility.Hint]]:
	"""The result without the block of a watched timing account that releases in the period the balance it carried
	into it, and a hint for each such release (steuerbote/ustva/carried.py)."""
	timing = TIMING_ACCOUNTS.get(mapping.chart, ())
	candidates = [account for account in result.unmapped if account in timing]
	if not candidates:
		return result, []
	balances = carried.carried_balances(closing_balances(company, period.end, candidates), lines)
	found = carried.releases(result.unmapped, lines, balances, timing)
	if not found:
		return result, []
	currency = frappe.get_cached_value("Company", company, "default_currency")
	names = account_labels(company, (release.account_number for release in found))
	hints = carried.release_hints(found, names, SiteFigures(currency))
	return replace(result, unmapped=carried.still_blocked(result.unmapped, found)), hints


def build_comparison(
	doc: Document,
	period: ustva.Period,
	settings: Document,
	mapping: ustva.Mapping,
	ledger: VatLedger | None = None,
) -> plausibility.Comparison:
	"""Vorperiodenvergleich: the amounts the return files against the previous period of its rhythm and
	against the same period a year earlier. A Kennzahl is flagged by the rule the report UStVA Kennzahlen
	filters its deviations with, on the thresholds of the settings.

	The earlier amounts come from the ledger, placed into periods by the same rule (``ledger``, read anew without
	one) and with the company's mapping validated
	against the form of their year, and never from earlier VAT Returns: the ledger is the single source of
	every Kennzahl, and the comparison has to work before any earlier return exists. A year without a catalogue
	of Kennzahlen, or with a form the mapping does not fit, leaves the amounts of its period empty and costs no
	query.
	"""
	thresholds = Thresholds.of(
		settings.get("comparison_threshold_percent"), settings.get("comparison_threshold_amount")
	)
	ledger = ledger or VatLedger.for_period(doc.company, period)
	return plausibility.compare(
		_read_rows(
			bridge.final_amounts, doc.kennzahlen, period.year, bridge.statutory_tax_of(doc.statutory_tax)
		),
		_earlier_period(ledger, period.previous(), settings, mapping),
		_earlier_period(ledger, year_before(period), settings, mapping),
		mapping.catalogue,
		thresholds.exceeded,
	)


def _earlier_period(
	ledger: VatLedger, period: ustva.Period, settings: Document, mapping: ustva.Mapping
) -> plausibility.EarlierPeriod:
	if prior_filings.lies_before_start(ledger.company, period.start):
		return plausibility.EarlierPeriod(period, None, plausibility.Code.BEFORE_START)
	try:
		mapping_of_the_year = mapping.for_year(period.year)
	except ustva.UnknownYearError:
		return plausibility.EarlierPeriod(period, None, plausibility.Code.NO_CATALOGUE)
	except ustva.MappingError:
		return plausibility.EarlierPeriod(period, None, plausibility.Code.MAPPING_UNFIT)
	result = _calculated(ledger.lines(period), mapping_of_the_year, period, settings)
	return plausibility.EarlierPeriod(
		period, {number: value.reported for number, value in result.values.items()}
	)


def late_change_rows(
	ledger: VatLedger, period: ustva.Period, settings: Document, mapping: ustva.Mapping
) -> list[dict]:
	"""Nach der Abgabe geändert: the bookings made after the filing of an earlier period that this return reports or
	that need the corrected return of their period, and the Kennzahlen of each period filed before it whose ledger
	amounts changed since its filing."""
	rows = late.current_rows(ledger.late(), period, ledger.outside)
	for filed_period in ledger.filed_before(period):
		rows.extend(_change_rows(ledger, filed_period, settings, mapping))
	return [_late_row(row) for row in rows]


def _change_rows(
	ledger: VatLedger, period: ustva.Period, settings: Document, mapping: ustva.Mapping
) -> list[late.Row]:
	"""The Kennzahlen of the filed period whose ledger amounts by today's ledger differ from those its return took;
	none for a period without a filed return or whose form the mapping does not fit."""
	filed = filed_amounts(ledger.company, period)
	if filed is None:
		return []
	try:
		mapping_of_the_year = mapping.for_year(period.year)
	except ustva.UnknownYearError, ustva.MappingError:
		return []
	now = _calculated(ledger.lines(period), mapping_of_the_year, period, settings)
	found = changes(filed, {number: value.amount for number, value in now.values.items()})
	currency = frappe.get_cached_value("Company", ledger.company, "default_currency")
	return late.change_rows(period, found, SiteFigures(currency).money)


def _late_row(row: late.Row) -> dict:
	return {
		"period_label": row.period.label,
		"kind": row.kind,
		"voucher_type": row.voucher_type or None,
		"voucher_no": row.voucher_no or None,
		"booked_at": row.booked_at,
		"message": _(row.template).format(*row.values),
		"needs_correction": row.needs_correction,
	}


def build_hints(
	doc: Document,
	period: ustva.Period,
	mapping: ustva.Mapping,
	result: ustva.UstvaResult,
	comparison: plausibility.Comparison,
	reconciliation: tuple[registers.Row, ...] = (),
	invoices_of_the_period: Collection[str] | None = None,
) -> tuple[plausibility.Hint, ...]:
	"""Hinweise: the invoices of the period, their reconciliation with the ledger, the balances on the accounts
	watched for a hint, the bases taken from the tax of a voucher without base account, the suppliers of the vouchers of
	sections C and D, the Vorperiodenvergleich, the confirmations of the USt-IdNrn. behind Kz 41, 42 and 21, the
	accounts of the tax templates without a place in the mapping and the differences of the reconciliation with the
	registers.

	A hint informs and never holds the return; whether it is ready follows the Verprobung and the accounts
	watched at the blocking level alone. ``invoices_of_the_period`` names the Sales Invoices whose bookings the
	return reports (sales_invoices), so the invoices meet the ledger amounts they belong to; without it the Sales
	Invoices posted in the period count.
	"""
	lines = invoices.load_lines(
		doc.company,
		period.start,
		period.end,
		plausibility.sales_accounts(mapping),
		plausibility.purchase_accounts(mapping),
		invoices_of_the_period,
	)
	ledger = {number: value.amount for number, value in result.values.items()}
	currency = frappe.get_cached_value("Company", doc.company, "default_currency")
	names = account_labels(doc.company, (balance.account_number for balance in result.hinted))
	figures = SiteFigures(currency)
	found = plausibility.hints(
		comparison,
		lines,
		ledger,
		mapping,
		figures,
		result.hinted,
		names,
		derived=result.derived,
		findings=result.findings,
	)
	vat_ids = period_vat_ids(doc.company, period, mapping)
	return plausibility.merged(
		found,
		vat_id_hints(doc.company, period, vat_ids.amounts),
		_tax_template_hints(doc.company, period, mapping, figures),
		registers.hints(
			reconciliation,
			account_labels(doc.company, (row.account_number for row in reconciliation if row.account_number)),
			figures,
		),
	)


def sales_invoices(lines: Iterable[ustva.LedgerLine]) -> list[str]:
	"""The Sales Invoices behind the ledger lines, each once."""
	prefix = f"{invoices.SALES.doctype}:"
	return sorted(
		{line.voucher.removeprefix(prefix) for line in lines if (line.voucher or "").startswith(prefix)}
	)


def build_reconciliation(
	company: str, period: ustva.Period, mapping: ustva.Mapping, lines: list[ustva.LedgerLine]
) -> tuple[registers.Row, ...]:
	"""Abgleich mit Registern: the reports Sales Register and Purchase Register of the period against the ledger lines
	the return is computed from, see steuerbote.ustva.registers."""
	return registers.reconcile(
		register_lines(company, period.start, period.end),
		lines,
		mapping,
		deliberately_without_kennzahl(mapping.chart),
	)


def _tax_template_hints(
	company: str, period: ustva.Period, mapping: ustva.Mapping, figures: plausibility.Figures
) -> list[plausibility.Hint]:
	"""A hint per account of the company's tax templates without a place in the mapping, with its balance in the
	period from the same query of the ledger as Berechnen, for these accounts only."""
	unplaced = tax_templates.without_place(
		template_accounts(company), mapping, deliberately_without_kennzahl(mapping.chart)
	)
	numbers = [account.account_number for account in unplaced if account.account_number]
	lines = load_lines(company, period.start, period.end, numbers) if numbers else []
	return tax_templates.hints(unplaced, tax_templates.balances(lines, numbers), figures)


def _figures(company: str) -> SiteFigures:
	return SiteFigures(frappe.get_cached_value("Company", company, "default_currency"))


class SiteFigures:
	"""The figures of a hint in the number format of the site, amounts in the company's currency."""

	def __init__(self, currency: str) -> None:
		self.currency = currency

	def money(self, amount: Decimal) -> str:
		return fmt_money(amount, currency=self.currency)

	def percent(self, value: Decimal) -> str:
		return f"{fmt_money(value, precision=1)} %"


@dataclass(frozen=True)
class PeriodVatIds:
	"""What the vouchers behind Kz 41, 42 and 21 of a period say of their customers: each voucher's amount with the
	customer's name and USt-IdNr., and the rows of steuerbote.zm that name the Customer behind each voucher."""

	amounts: list[VoucherAmount]
	vouchers: list[dict]


def period_vat_ids(company: str, period: ustva.Period, mapping: ustva.Mapping) -> PeriodVatIds:
	"""The vouchers behind Kz 41, 42 and 21 of the period from the ledger, and the customers they name, read as the
	Zusammenfassende Meldung reads them (steuerbote.zm_sources): a Sales Invoice with the USt-IdNr. it was made
	with, a Payment Entry or a Journal Entry with that of the Sales Invoice it refers to."""
	shares = zm_sources.span_shares(company, (period.start, period.end), mapping)
	parties = zm_sources.parties(item.voucher for item in shares)
	amounts = zm_bridge.voucher_amounts_of(shares, parties)
	return PeriodVatIds(amounts, zm_bridge.voucher_rows(amounts, parties))


def vat_id_hints(company: str, period: ustva.Period, amounts: list[VoucherAmount]) -> list[plausibility.Hint]:
	"""The hints on the USt-IdNrn. of the vouchers: the latest VAT ID Confirmation of each number of the company,
	from a Zusammenfassende Meldung or a Voranmeldung, and the age the VAT Return Settings allow."""
	latest = vat_id_confirmation.latest(company, plausibility.confirmable(amounts))
	age = bridge.max_confirmation_age(frappe.db.get_value(SETTINGS_DOCTYPE, company, "max_confirmation_age"))
	return plausibility.vat_id_hints(amounts, bridge.latest_confirmations(latest), period, age)


def run_confirmation(name: str) -> None:
	"""Background job of VATReturn.confirm_vat_ids, see confirming.run: then the hints on the USt-IdNrn. show the
	latest confirmations."""
	confirming.run(DOCTYPE, name, UrllibFetch, _clock)


def _clock() -> datetime:
	return datetime.now(UTC)
