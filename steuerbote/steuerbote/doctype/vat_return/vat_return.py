"""VAT Return: the Umsatzsteuer-Voranmeldung of one company for one Voranmeldungszeitraum.

"Berechnen" (calculate) reads the period's general ledger through steuerbote.ledger, the company's VAT
Return Mapping and VAT Return Settings, and leaves every amount to the core in steuerbote.ustva; bridge.py
maps the results onto the tables. A company can switch between monthly and quarterly filing at the start of
a quarter, so a period number alone names a month or a quarter: the return carries its rhythm, which has to
be the one the settings prescribe for the first month of the period. An override replaces a computed amount
once it has a reason, and the totals and Kz 83 always follow the amounts as filed. A period is filed once;
every further return for it is a corrected return (Kz 10), and filing one marks the returns before it as
replaced. "XML für Mein ELSTER" (make_import_file) writes the return as saved into the file for the import
into Mein ELSTER through steuerbote.elster.ustva_xml and attaches it to the return.

"Prüfen", "Testsenden" and "Senden" (transmit) run in a background job: the job writes the same tree as the
file for Mein ELSTER with the Hersteller-ID for ERiC and hands it to steuerbote.eric, through the worker of an
installed runtime or the simulation; every run is recorded as an ELSTER Transmission. While it runs, the return
cannot change, so that the job files exactly what it sent. Only a successful real Senden submits the return,
which files it; "In Mein ELSTER abgegeben" and "Als außerhalb abgegeben vermerken" (mark_filed_outside) submit
it with a note instead. Submitting alone ("Buchen") files nothing and is refused, except for a return that
ELSTER accepted while its submission failed. A period counts as filed once a return of it is submitted or
another return of it was filed through Steuerbote, cancelled or not, and a return with a record of its filing
cannot be cancelled. Certificate and password never become arguments of the job: stash_certificate keeps
them encrypted for a few minutes and the job takes them back by their token.
"""

import base64
import binascii
import contextlib
import re

import frappe
from frappe import _
from frappe.core.doctype.file.utils import get_content_hash
from frappe.model.document import Document
from frappe.utils import cint, escape_html, getdate, now_datetime, strip_html
from frappe.utils.background_jobs import is_job_enqueued

import steuerbote
from steuerbote import ustva
from steuerbote.elster import ustva_xml
from steuerbote.eric import secrets
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import TESTMERKER, Operation, Outcome
from steuerbote.eric.service import PIN
from steuerbote.ledger import account_names, accounts_without_number, load_lines
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import (
	EXTERN,
	FAILED,
	FILED_VIA,
	OTHER_WAY,
	RUNNING,
	SEND,
	SUCCEEDED,
	TEST_SEND,
	UNKNOWN,
	VALIDATE,
)
from steuerbote.steuerbote.doctype.eric_settings.eric_settings import eric_log_root
from steuerbote.steuerbote.doctype.vat_return import bridge, transmission_adapter
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors

DOCTYPE = "VAT Return"
SETTINGS_DOCTYPE = "VAT Return Settings"
MAPPING_DOCTYPE = "VAT Return Mapping"
ERIC_SETTINGS = "ERiC Settings"
TRANSMISSION = "ELSTER Transmission"

DRAFT = "Entwurf"
CALCULATED = "Berechnet"
READY = "Bereit"
FILED = "Abgegeben"
REPLACED = "Ersetzt"

PERIOD_FIELDS = ("company", "year", "rhythm", "period_index")
CALCULATED_TABLES = ("kennzahlen", "checks", "deviations", "unmapped")

OPERATIONS = (VALIDATE, TEST_SEND, SEND)
LOCK_FIELD = "transmission_in_progress"
TRANSMISSION_JOB = "steuerbote.steuerbote.doctype.vat_return.vat_return.run_transmission"
TRANSMISSION_EVENT = "steuerbote_elster_transmission"
# The worker of steuerbote.eric is ended after two minutes; the job keeps time to record the result.
TRANSMISSION_TIMEOUT = 300
# One case per delivery, so its NutzdatenTicket is 1 (ERiC-Entwicklerhandbuch 44.3.6.0, p. 95).
NUTZDATEN_TICKET = "1"
# Kz 09 and the header of the simulation: five digits as ELSTER wants them, and no Hersteller-ID anyone has.
SIMULATION_HERSTELLER_ID = "00000"
DEFAULT_PRODUKT_NAME = "steuerbote"
# The .pfx file of an ELSTER certificate has a few kilobytes.
MAX_CERTIFICATE_BYTES = 64 * 1024
# TransferTicketSType in headerbasis_datentypen.xsd of the ELSTER Basisschema.
TRANSFERTICKET = re.compile(r"[0-9a-km-z]{2}[0-9]{3}[0-9a-km-z]{27}")


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
		kz500_begruendung: DF.SmallText | None
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
		transmission_in_progress: DF.Check
		unmapped: DF.Table[VATReturnUnmappedAccount]
		year: DF.Int
	# end: auto-generated types

	def onload(self) -> None:
		"""Tell the form whether ERiC runs as a simulation, whether the lock of a transmission is stale and
		whether ELSTER accepted the return while its submission failed, for its banner and its buttons."""
		simulation = frappe.get_cached_doc(ERIC_SETTINGS).simulation
		draft = self.docstatus == 0 and not self.is_new()
		self.set_onload(
			"elster",
			{
				"simulation": bool(cint(simulation)),
				"stale": draft and self._has_stale_transmission(),
				"sent": draft and self._was_accepted(),
			},
		)

	def validate(self):
		self._refuse_changes_while_transmitting()
		if self._lacks_mandatory_values():
			return  # the mandatory check that follows names the missing fields
		self._require_catalogue()
		self._set_period()
		self._refuse_second_return()
		self._discard_calculation_of_another_period()
		self._set_final_amounts()
		self._check_supplementary_details()

	def before_submit(self):
		if not (self.flags.filing_transmission or self.flags.filed_outside or self._was_accepted()):
			frappe.throw(
				_(
					"A VAT Return is filed through Senden or by noting its filing in Mein ELSTER or outside Steuerbote, not by Buchen alone."
				)
			)
		self._check_fit_for_filing()
		self.status = FILED

	def before_cancel(self):
		if any(row.status == SUCCEEDED for row in filings([self.name])):
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
	def transmit(self, operation: str, token: str | None = None) -> str:
		"""Prüfen, Testsenden or Senden: check that the return can go, then run it in a background job.

		Certificate and password reach the job only as ``token`` from stash_certificate(), never as arguments
		of the job. Returns the name of the ELSTER Transmission that records the run.
		"""
		if operation not in OPERATIONS:
			frappe.throw(_("Steuerbote knows no ELSTER procedure {0}.").format(escape_html(str(operation))))
		self.check_permission("submit" if operation == SEND else "write")
		self._lock_for_transmission()
		if self.docstatus != 0:
			frappe.throw(
				_(
					"Only a draft return can be transmitted. A filed return is corrected by a corrected return (Kz 10)."
				)
			)
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the return before transmitting it."))
		self._close_stale_transmission()
		settings = frappe.get_single(ERIC_SETTINGS)
		simulation = bool(cint(settings.simulation))
		if not simulation:
			require_privacy_notice(settings)
		if operation == SEND:
			self._check_can_be_sent(simulation)
		if operation != VALIDATE and not simulation and not token:
			frappe.throw(_("Choose the certificate file and enter its password."))
		transmission = self._new_transmission(operation, simulated=simulation)
		self.db_set(LOCK_FIELD, 1)
		frappe.enqueue(
			TRANSMISSION_JOB,
			queue="long",
			timeout=TRANSMISSION_TIMEOUT,
			job_id=transmission_job_id(transmission.name),
			enqueue_after_commit=True,
			name=self.name,
			operation=operation,
			token=token,
			transmission=transmission.name,
		)
		return transmission.name

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
		self._lock_for_transmission()
		if self.docstatus != 0:
			frappe.throw(_("Only a draft return can be marked as filed."))
		accepted = [row for row in filings([self.name]) if row.status == SUCCEEDED]
		if accepted:
			frappe.throw(
				_(
					"ELSTER accepted {0} with Transferticket {1}, so it was not filed outside Steuerbote: submit it with Buchen."
				).format(self.name, accepted[0].transferticket)
			)
		self._refuse_second_filing()
		self.flags.filed_outside = True
		self.submit()
		return self._new_transmission(
			EXTERN,
			simulated=False,
			status=SUCCEEDED,
			remarks=note or None,
			filed_via=filed_via,
			transferticket=ticket or None,
			filed_on=filed_date,
		).name

	@frappe.whitelist(methods=["POST"])
	def release_stale_transmission(self) -> None:
		"""Close the run whose background job is gone, a worker that stopped for instance, and lift its lock,
		so that the return can be used again; the form calls this when it finds such a lock."""
		self.check_permission("write")
		self._lock_for_transmission()
		self._close_stale_transmission()

	def _check_fit_for_filing(self) -> None:
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the return before submitting it."))
		if not self.ready and not (self.remarks or "").strip():
			frappe.throw(
				_(
					"The return is not ready: a Verprobung deviates or a watched account has a balance. Explain in the remarks why it is filed nonetheless."
				)
			)

	def _check_can_be_sent(self, simulation: bool) -> None:
		"""Senden files the return, once: it needs ERiC, the return fit for filing and no earlier filing."""
		if simulation:
			frappe.throw(
				_(
					"Senden needs an installed ERiC runtime and a Hersteller-ID. In the simulation, only Prüfen and Testsenden are possible."
				)
			)
		self._check_fit_for_filing()
		sent = filings([self.name])
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
		sent = filings(others)
		if sent:
			frappe.throw(
				_(
					"{0} of {1} was transmitted already as {2}. Mark this return as a corrected return (Kz 10)."
				).format(self.period_label, self.company, sent[0].vat_return)
			)

	def _lock_for_transmission(self) -> None:
		"""Hold the row of the return until the request ends and read it fresh: two requests cannot start a
		transmission together, and every check sees what the job will send."""
		frappe.db.get_value(DOCTYPE, self.name, "name", for_update=True)
		self.reload()

	def _refuse_changes_while_transmitting(self) -> None:
		"""The job files exactly what it sent, so the return stays as it is while a transmission runs. The
		flag in the database counts: the form may hold a copy from before the transmission started."""
		if self.is_new() or self.flags.filing_transmission:
			return
		if cint(frappe.db.get_value(DOCTYPE, self.name, LOCK_FIELD)):
			frappe.throw(
				_("A transmission of this return is running. Wait for its result before changing the return.")
			)

	def _close_stale_transmission(self) -> None:
		"""Refuse a second run while one is queued or running; close the record of a run whose job is gone
		and lift the lock."""
		if not cint(self.transmission_in_progress):
			return
		running = self._running_transmissions()
		if any(is_job_enqueued(transmission_job_id(name)) for name in running):
			frappe.throw(_("A transmission of this return is running. Wait for its result."))
		for name in running:
			close_stale_transmission(frappe.get_doc(TRANSMISSION, name))
		self.db_set(LOCK_FIELD, 0)

	def _has_stale_transmission(self) -> bool:
		if not cint(self.transmission_in_progress):
			return False
		return not any(is_job_enqueued(transmission_job_id(name)) for name in self._running_transmissions())

	def _running_transmissions(self) -> list[str]:
		return frappe.get_all(
			TRANSMISSION, filters={"vat_return": self.name, "status": RUNNING}, pluck="name"
		)

	def _was_accepted(self) -> bool:
		"""Whether ELSTER accepted a real Senden of the return."""
		return any(row.operation == SEND and row.status == SUCCEEDED for row in filings([self.name]))

	def _new_transmission(
		self,
		operation: str,
		*,
		simulated: bool,
		status: str = RUNNING,
		remarks: str | None = None,
		filed_via: str | None = None,
		transferticket: str | None = None,
		filed_on=None,
	) -> Document:
		now = now_datetime()
		return frappe.get_doc(
			{
				"doctype": TRANSMISSION,
				"vat_return": self.name,
				"company": self.company,
				"operation": operation,
				"status": status,
				"simulated": int(simulated),
				"user": frappe.session.user,
				"started_at": now,
				"finished_at": None if status == RUNNING else now,
				"remarks": remarks,
				"filed_via": filed_via,
				"transferticket": transferticket,
				"filed_on": filed_on,
			}
		).insert(ignore_permissions=True)

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
		"""Kz 500 and its Begründung go together, the Begründung on one line ELSTER takes."""
		with xml_errors(_("VAT Return")):
			ustva_xml.supplementary_details(self.supplementary_code, self.kz500_begruendung)

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


def filings(returns: list[str]) -> list[dict]:
	"""The records of the given returns that file them, or may have: a real Senden that ELSTER accepted or
	whose outcome is unknown, and a filing outside Steuerbote; the latest first. A cancelled return counts
	as well, since cancelling it in ERPNext takes nothing back from the Finanzamt."""
	if not returns:
		return []
	return frappe.get_all(
		TRANSMISSION,
		filters={
			"vat_return": ["in", returns],
			"operation": ["in", (SEND, EXTERN)],
			"status": ["in", (SUCCEEDED, UNKNOWN)],
			"simulated": 0,
		},
		fields=["name", "vat_return", "operation", "status", "transferticket"],
		order_by="creation desc",
	)


def transmission_job_id(transmission: str) -> str:
	return f"steuerbote:elster:{transmission}"


def close_stale_transmission(transmission: Document) -> None:
	"""Close a run whose job is gone. A check never left the server, a test send or a send may have
	reached ELSTER, so its outcome is unknown."""
	transferred = transmission.operation in (TEST_SEND, SEND) and not cint(transmission.simulated)
	outcome = Outcome.UNKNOWN if transferred else Outcome.FAILED
	transmission.update(
		{
			"status": UNKNOWN if transferred else FAILED,
			"outcome": outcome.value,
			"finished_at": now_datetime(),
		}
	)
	note = (
		_(
			"The transmission did not finish and its result is unknown. Before sending again, check in Mein ELSTER whether the return arrived."
		)
		if transferred
		else _(
			"The run did not finish because its background job is gone. Nothing reached ELSTER; start it again."
		)
	)
	transmission.append("messages", {"severity": "error", "text": note})
	record(transmission)


def require_privacy_notice(settings: Document) -> None:
	"""ERiC licence, § 5 Abs. 1 and 2: the end user acknowledges the Datenschutzhinweise of the tax
	administration before using the software."""
	if not cint(settings.privacy_notice_confirmed):
		frappe.throw(
			_(
				"Before ERiC is used, the Datenschutzhinweise of the tax administration have to be read and confirmed in the ERiC Settings."
			)
		)


def record(transmission: Document) -> None:
	"""Save an ELSTER Transmission, which only the server may change."""
	transmission.flags.recording = True
	transmission.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def stash_certificate(certificate_secret: str, certificate_password: str) -> str:
	"""Keep the certificate (.pfx, base64) and its password for the next transmission in the one-shot store
	of steuerbote.eric.secrets; returns the token that transmit() takes in their place.

	Parameters and locals carry "secret" or "password" in their names, which Frappe masks in its logs and
	tracebacks.
	"""
	frappe.has_permission(DOCTYPE, "write", throw=True)
	try:
		decoded_secret = base64.b64decode(certificate_secret or "", validate=True)
	except binascii.Error, ValueError:
		decoded_secret = b""
	if not decoded_secret or len(decoded_secret) > MAX_CERTIFICATE_BYTES:
		frappe.throw(_("The certificate file could not be read. Choose the .pfx file of the ELSTER account."))
	if not PIN.fullmatch(certificate_password or ""):
		frappe.throw(
			_(
				"The certificate password has 6 to 128 characters: letters, digits, spaces and punctuation, without umlauts."
			)
		)
	return secrets.stash(decoded_secret, certificate_password)


def run_transmission(name: str, operation: str, transmission: str, token: str | None = None) -> None:
	"""Background job of VATReturn.transmit: one run through ERiC or its simulation.

	Whatever happens ends in the ELSTER Transmission, the lock of the return is released and the user who
	started the run gets a realtime notice. Only a Senden that ELSTER accepted changes the return: the job
	submits it, which files it. A run whose record was closed meanwhile as stale does nothing, since the lock
	of the return may belong to another run by now, and drops its certificate from the store.
	"""
	transmission = frappe.get_doc(TRANSMISSION, transmission)
	if transmission.status != RUNNING:
		_discard_certificate(token)
		return
	result = None
	frappe.db.savepoint("elster_transmission")
	try:
		result, nutzdaten = _call_eric(name, Operation(operation), token, transmission)
		_record_result(transmission, result, nutzdaten)
		if _files_the_return(result):
			_file_sent_return(name, transmission)
	except Exception as error:
		frappe.db.rollback(save_point="elster_transmission")
		_record_failure(transmission, _failure_text(error), result)
	finally:
		frappe.db.set_value(DOCTYPE, name, LOCK_FIELD, 0)
	frappe.publish_realtime(
		TRANSMISSION_EVENT,
		{
			"vat_return": name,
			"transmission": transmission.name,
			"operation": transmission.operation,
			"status": transmission.status,
			"simulated": cint(transmission.simulated),
		},
		user=transmission.user,
		after_commit=True,
	)


def _call_eric(name: str, operation: Operation, token: str | None, transmission: Document):
	doc = frappe.get_doc(DOCTYPE, name)
	settings = frappe.get_single(ERIC_SETTINGS)
	simulation = bool(cint(settings.simulation))
	if not simulation:
		require_privacy_notice(settings)
	certificate_secret, certificate_password = _take_certificate(token)
	header = envelope_header(doc, settings, operation, simulation)
	nutzdaten = doc.nutzdaten(header.hersteller_id)
	runtime_info = (
		None if simulation else _installed_runtime(doc, operation, header.hersteller_id, transmission)
	)
	result = transmission_adapter.run(
		operation, nutzdaten, header, runtime_info, certificate_secret, certificate_password
	)
	return result, nutzdaten


def envelope_header(
	doc: Document, settings: Document, operation: Operation, simulation: bool
) -> EnvelopeHeader:
	"""The header of the delivery. Its Hersteller-ID is the one of the ERiC Settings, which the runtime and
	Kz 09 of the Nutzdaten carry as well; only the simulation runs without one."""
	hersteller_id = settings.hersteller_id or (SIMULATION_HERSTELLER_ID if simulation else "")
	datenlieferant = settings.datenlieferant or (doc.company if simulation else "")
	if not hersteller_id:
		frappe.throw(_("Enter the Hersteller-ID in the ERiC Settings."))
	if not datenlieferant:
		frappe.throw(_("Enter the Datenlieferant in the ERiC Settings."))
	return EnvelopeHeader(
		hersteller_id=hersteller_id,
		datenlieferant=datenlieferant,
		produkt_name=settings.produkt_name or DEFAULT_PRODUKT_NAME,
		produkt_version=steuerbote.__version__,
		empfaenger_finanzamt=finanzamt_of(doc.company),
		datenart_version=f"UStVA_{cint(doc.year)}",
		testmerker=TESTMERKER if operation is Operation.TEST_SEND else None,
		nutzdaten_ticket=NUTZDATEN_TICKET,
	)


def finanzamt_of(company: str) -> str:
	"""The Bundesfinanzamtsnummer: "die ersten 4 Stellen der 13-stelligen Steuernummer" (ERiC-API-Referenz)."""
	elster_tax_number = settings_for(company).elster_tax_number
	if not elster_tax_number:
		frappe.throw(_("The VAT Return Settings of {0} have no ELSTER Steuernummer.").format(company))
	return elster_tax_number[:4]


def _take_certificate(token: str | None) -> tuple[bytes | None, str | None]:
	if not token:
		return None, None
	try:
		return secrets.take(token)
	except secrets.SecretsExpired:
		frappe.throw(
			_(
				"The certificate and its password are no longer available. Start the transmission again and enter them anew."
			)
		)


def _discard_certificate(token: str | None) -> None:
	if token:
		with contextlib.suppress(secrets.SecretsExpired):
			secrets.take(token)


def _installed_runtime(doc: Document, operation: Operation, hersteller_id: str, transmission: Document):
	"""The runtime for the year of the return; ERiC writes its eric.log beside the site, one per run."""
	log_dir = eric_log_root() / transmission.name
	runtime_info = transmission_adapter.detect_runtime(cint(doc.year), operation, hersteller_id, log_dir)
	if runtime_info is None:
		frappe.throw(
			_(
				"No installed ERiC runtime serves {0}. Install the runtime for this year in the ERiC Settings; a beta serves Testsenden only."
			).format(cint(doc.year))
		)
	return runtime_info


def _status(result) -> str:
	if result.ok:
		return SUCCEEDED
	return UNKNOWN if result.outcome is Outcome.UNKNOWN else FAILED


def _files_the_return(result) -> bool:
	return result.operation is Operation.SEND and result.outcome is Outcome.ACCEPTED and not result.simulated


def _record_result(transmission: Document, result, nutzdaten: str) -> None:
	transmission.reload()
	transmission.update(
		{
			"status": _status(result),
			"outcome": result.outcome.value,
			"simulated": int(result.simulated),
			"eric_version": result.eric_version,
			"transferticket": result.transferticket,
			"testmerker": result.testmerker,
			"finished_at": now_datetime(),
		}
	)
	transmission.set("messages", _message_rows(result))
	response = result.server_response_xml
	files = {
		"xml": ("nutzdaten.xml", nutzdaten.encode()),
		"protocol_pdf": ("protokoll.pdf", result.protocol_pdf),
		"response_xml": ("serverantwort.xml", response.encode() if response else None),
	}
	for fieldname, (suffix, content) in files.items():
		transmission.set(fieldname, _attach_to_transmission(transmission, fieldname, suffix, content))
	record(transmission)


def _message_rows(result) -> list[dict]:
	return [
		{"severity": message.severity, "code": message.code, "text": message.text, "field": message.field}
		for message in result.messages
	]


def _attach_to_transmission(
	transmission: Document, fieldname: str, suffix: str, content: bytes | None
) -> str | None:
	"""A private File on the ELSTER Transmission; returns its address for the field.

	A file that cannot be stored is named in the messages instead: the record of the run, its Transferticket
	above all, matters more than any one of its files.
	"""
	if not content:
		return None
	file_name = f"{transmission.vat_return}-{transmission.operation}-{suffix}"
	frappe.db.savepoint("elster_file")
	try:
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"attached_to_doctype": TRANSMISSION,
				"attached_to_name": transmission.name,
				"attached_to_field": fieldname,
				"is_private": 1,
				"content": content,
			}
		).insert(ignore_permissions=True)
	except Exception as error:
		frappe.db.rollback(save_point="elster_file")
		transmission.append(
			"messages",
			{
				"severity": "error",
				"text": _("The file {0} of the transmission could not be stored: {1}").format(
					file_name, _failure_text(error)
				),
			},
		)
		return None
	return file.file_url


def _file_sent_return(name: str, transmission: Document) -> None:
	"""Submit the return the Finanzamt has now. If that fails, the record says so: sending it again would
	file it twice."""
	frappe.db.savepoint("elster_filing")
	try:
		doc = frappe.get_doc(DOCTYPE, name)
		doc.flags.filing_transmission = transmission.name
		doc.submit()
	except Exception as error:
		frappe.db.rollback(save_point="elster_filing")
		transmission.reload()
		transmission.append(
			"messages", {"severity": "error", "text": _not_filed_text(transmission, _failure_text(error))}
		)
		record(transmission)


def _record_failure(transmission: Document, text: str, result) -> None:
	"""Record a run that broke off; with the result of ERiC, what ERiC answered is kept, the Transferticket
	of a Senden above all."""
	transmission.reload()
	outcome = result.outcome if result else Outcome.FAILED
	transmission.update(
		{
			"status": _status(result) if result else FAILED,
			"outcome": outcome.value,
			"finished_at": now_datetime(),
		}
	)
	if result:
		transmission.update(
			{
				"simulated": int(result.simulated),
				"eric_version": result.eric_version,
				"transferticket": result.transferticket,
				"testmerker": result.testmerker,
			}
		)
		transmission.set("messages", _message_rows(result))
		if _files_the_return(result):
			text = _not_filed_text(transmission, text)
	transmission.append("messages", {"severity": "error", "text": text})
	record(transmission)


def _not_filed_text(transmission: Document, reason: str) -> str:
	return _(
		"Transmitted with Transferticket {0}, but the return could not be submitted: {1} Do not send it again; submit the return once the cause is resolved."
	).format(transmission.transferticket, reason)


def _failure_text(error: Exception) -> str:
	"""What the user reads about a failure: the message of an expected error, else a pointer to the Error Log."""
	if isinstance(error, frappe.ValidationError | ValueError):
		return strip_html(str(error)).strip()
	frappe.log_error(title=_("ELSTER transmission failed"))
	return _("An unexpected error stopped the transmission. The Error Log has the details.")
