"""USt-IdNrn. prüfen: the confirmation of the USt-IdNrn. of a document at the BZSt in a background job, the same for
every document whose USt-IdNrn. Steuerbote confirms.

A document whose USt-IdNrn. Steuerbote confirms inherits Confirming before Document, has the fields company and
confirmation_in_progress and provides numbers_to_confirm(), the numbers its job asks about; details_for(vat_id),
name and address of the customer for the qualified query, or None; party_for(vat_id), the customer whose number it
is, or None; and take_in_confirmations(), which shows the latest confirmations once the job has stored them. Its whitelisted confirm_vat_ids checks what its document needs
and hands the numbers to start_confirmation, which refuses a second run while one is queued or running, needs the
company's own German USt-IdNr. and puts the run into the queue long, one job per document. The job of its module
calls run() with the transport and the clock of that module.

run() asks steuerbote.vatid about one number after the other and about none twice, leaves out a number a query of
today has answered already (steuerbote.vatid.partners.covered_today), wherever it was asked, and stores each
confirmation as a VAT ID Confirmation that names the customer, committed at once: the record is the proof of queries the service received (UStAE 18e.1
Abs. 2 Satz 5), which nothing that fails later may take back. While the run is queued or running, the document
does not change; a lock whose job is gone is released by the form or by the next run.
"""

from collections.abc import Callable, Collection

import frappe
from frappe import _
from frappe.utils import cint, getdate, strip_html
from frappe.utils.background_jobs import is_job_enqueued

from steuerbote import vatid
from steuerbote.steuerbote import partner_vat_ids
from steuerbote.steuerbote.doctype.vat_id_confirmation import vat_id_confirmation
from steuerbote.vatid.partners import covered_today
from steuerbote.vatid.transport import Clock, Fetch

LOCK_FIELD = "confirmation_in_progress"
CONFIRMATION_EVENT = "steuerbote_vat_id_confirmation"
SETTINGS_DOCTYPE = "VAT Return Settings"
# A confirmation asks at most three times, the simple and the qualified query and VIES, and UrllibFetch waits
# up to a minute for each answer.
SECONDS_PER_NUMBER = 200
MINIMUM_TIMEOUT = 300
CALCULATED_STATUSES = ("Berechnet", "Bereit")


class Confirming:
	"""A document whose USt-IdNrn. Steuerbote confirms at the BZSt, mixed into its controller before Document."""

	def confirmation_state(self) -> dict:
		"""For the form: whether the lock of a confirmation is stale, so that the form releases it, and for a
		calculated draft the numbers a confirmation would ask about now and the own USt-IdNr. it would send, which
		its dialog names."""
		draft = self.docstatus == 0 and not self.is_new()
		state = {"stale": draft and self._has_stale_confirmation(), "numbers": [], "requester": None}
		if draft and self.get("status") in CALCULATED_STATUSES and not cint(self.get(LOCK_FIELD)):
			ust_idnr = frappe.db.get_value(SETTINGS_DOCTYPE, self.company, "ust_idnr")
			state["requester"] = vatid.normalize(ust_idnr) if vatid.is_german(ust_idnr) else None
			shown = len(frappe.local.message_log)
			try:
				state["numbers"] = self.pending_numbers()
			except frappe.ValidationError, ValueError:
				del frappe.local.message_log[shown:]
		return state

	def pending_numbers(self) -> list[str]:
		"""The numbers to confirm that no query of today has answered already."""
		today = getdate()
		return [
			number
			for number in self.numbers_to_confirm()
			if not covered_today(
				partner_vat_ids.today_queries(self.company, number, today), self.details_for(number)
			)
		]

	@frappe.whitelist(methods=["POST"])
	def release_stale_confirmation(self) -> None:
		"""Lift the lock of a confirmation whose background job is gone; the form calls this when it finds one.
		What the job stored before it stopped stays, and the next confirmation or Berechnen shows it."""
		self.check_permission("write")
		self.lock_for_confirmation()
		self._close_stale_confirmation()

	def lock_for_confirmation(self) -> None:
		"""Hold the row of the document until the request ends and read it fresh."""
		frappe.db.get_value(self.doctype, self.name, "name", for_update=True)
		self.reload()

	def start_confirmation(self, numbers: Collection[str], job: str, nothing_to_confirm: str) -> int:
		"""Put the confirmation of ``numbers`` into the background ``job``, which the queue long runs under a job id of
		the document; returns how many numbers the job asks about."""
		self._close_stale_confirmation()
		requester(self.company)
		if not numbers:
			frappe.throw(nothing_to_confirm)
		numbers = [number for number in numbers if number in set(self.pending_numbers())]
		if not numbers:
			frappe.throw(_("Every USt-IdNr. of {0} was confirmed today already.").format(self.name))
		self.db_set(LOCK_FIELD, 1)
		frappe.enqueue(
			job,
			queue="long",
			timeout=max(MINIMUM_TIMEOUT, SECONDS_PER_NUMBER * len(numbers)),
			job_id=confirmation_job_id(self.name),
			enqueue_after_commit=True,
			name=self.name,
		)
		return len(numbers)

	def refuse_changes_while_confirming(self) -> None:
		"""The job takes the confirmations into the document, so it stays as it is while a confirmation runs. The flag
		in the database counts: the form may hold a copy from before the confirmation started."""
		if self.is_new() or self.flags.confirming:
			return
		if cint(frappe.db.get_value(self.doctype, self.name, LOCK_FIELD)):
			frappe.throw(
				_(
					"The USt-IdNrn. of {0} are being confirmed. Wait for the result before changing it."
				).format(self.name)
			)

	def refuse_while_confirming(self) -> None:
		"""Refuse what has to wait for the confirmation that runs, such as a transmission."""
		if cint(self.get(LOCK_FIELD)):
			frappe.throw(
				_("The USt-IdNrn. of {0} are being confirmed. Wait for the result.").format(self.name)
			)

	def _close_stale_confirmation(self) -> None:
		if not cint(self.get(LOCK_FIELD)):
			return
		if is_job_enqueued(confirmation_job_id(self.name)):
			frappe.throw(
				_("The USt-IdNrn. of {0} are being confirmed. Wait for the result.").format(self.name)
			)
		self.db_set(LOCK_FIELD, 0)

	def _has_stale_confirmation(self) -> bool:
		return bool(cint(self.get(LOCK_FIELD))) and not is_job_enqueued(confirmation_job_id(self.name))


def requester(company: str) -> str:
	"""The company's own German USt-IdNr., with which it asks the BZSt about the numbers of its customers."""
	ust_idnr = frappe.db.get_value(SETTINGS_DOCTYPE, company, "ust_idnr")
	if not vatid.is_german(ust_idnr):
		frappe.throw(
			_(
				"Enter the USt-IdNr. of {0} in the VAT Return Settings, DE and nine digits, before confirming USt-IdNrn."
			).format(company)
		)
	return vatid.normalize(ust_idnr)


def confirmation_job_id(name: str) -> str:
	return f"steuerbote:ustid:{name}"


def run(doctype: str, name: str, fetch: Callable[[], Fetch], clock: Clock) -> None:
	"""The background job of USt-IdNrn. prüfen at the document ``name`` of ``doctype``: one confirmation per number
	the document gives, one query after the other and none repeated, each confirmation with a transport of its own
	from ``fetch``, which keeps the cookies of the services, and the time from ``clock``.

	Each confirmation is committed as soon as it is stored: it is the proof of queries the service received, which
	nothing that fails later may take back. Then the document takes in the latest confirmations, the lock is
	released, and the user who started the job gets a realtime notice that names the document.
	"""
	user = frappe.session.user
	confirmed: list[str] = []
	failed: list[str] = []
	error_text = None
	try:
		doc = frappe.get_doc(doctype, name)
		asking = requester(doc.company)
		for vat_id in doc.numbers_to_confirm():
			details = doc.details_for(vat_id)
			if covered_today(partner_vat_ids.today_queries(doc.company, vat_id, getdate()), details):
				continue
			customer = doc.party_for(vat_id)
			party = (partner_vat_ids.CUSTOMER, customer) if customer else None
			frappe.db.savepoint("vat_id_confirmation")
			try:
				answer = vatid.confirm(vat_id, asking, details, fetch(), clock)
				vat_id_confirmation.store(
					answer, doc.company, (doctype, name), party=party, started_by=doctype
				)
				frappe.db.commit()
				confirmed.append(vat_id)
				if customer:
					partner_vat_ids.refresh_status(partner_vat_ids.CUSTOMER, customer)
			except Exception:
				frappe.db.rollback(save_point="vat_id_confirmation")
				frappe.log_error(title=_("Confirmation of a USt-IdNr. failed"))
				failed.append(vat_id)
		doc.reload()
		doc.take_in_confirmations()
	except Exception as error:
		frappe.db.rollback()
		error_text = _failure_text(error)
	finally:
		frappe.db.set_value(doctype, name, LOCK_FIELD, 0)
	frappe.publish_realtime(
		CONFIRMATION_EVENT,
		{
			"document_type": doctype,
			"document": name,
			"confirmed": len(confirmed),
			"failed": failed,
			"error": error_text,
		},
		user=user,
		after_commit=True,
	)


def _failure_text(error: Exception) -> str:
	"""What the user reads about a failure: the message of an expected error, else a pointer to the Error Log."""
	if isinstance(error, frappe.ValidationError | ValueError):
		return strip_html(str(error)).strip()
	frappe.log_error(title=_("Confirmation of the USt-IdNrn. failed"))
	return _("An unexpected error stopped the confirmation. The Error Log has the details.")
