"""The Frappe layer the annual documents of stage 3 share: AnnualFiling, mixed into each controller before
Transmittable, where the document goes to ELSTER through ERiC, and before Document.

The Umsatzsteuererklärung, the E-Bilanz, the Körperschaft- and the Gewerbesteuererklärung and the Jahresabschluss live
the same way, so AnnualFiling generalises the rules of the VAT Return and the Zusammenfassende Meldung
(docs/architektur.md, „Lebenslauf einer Meldung“); its pure core is steuerbote/jahresmeldung:

- Only Steuerbote sets the status, by the moves of its lifecycle (FILING or ACCOUNTS of jahresmeldung.lifecycle).
- Berechnen (calculate) asks the module for what it computed (compute), keeps the corrections and the lines by hand
  (jahresmeldung.overrides), adds the checks of the values as filed (check_reported), and sets the findings, „Bereit
  zur Abgabe“ and the status from both (jahresmeldung.findings).
- Frappe keeps no read-only field from a save through its API, so a save takes only what the company enters: the
  corrections and lines by hand with their reasons, the remarks and the fields of the module that are no
  calculation. What Berechnen computed, the findings, the status and the filing stay as stored, and a save that
  changes what a line reports leaves the document Berechnet until Berechnen checks it again. Another key discards the
  calculation, and a key holds one draft and one filing, a further filing being a Berichtigung of a filed document
  of the key (jahresmeldung.corrections says how each Datenart marks it).
- Before a document is transmitted, made into a file or submitted, the amounts of its lines are computed again from
  what they hold (require_amounts_as_stored).
- An Erklärung and the E-Bilanz are filed through an accepted Senden or the note of their filing, never by Buchen
  alone, and nothing filed is cancelled. A Jahresabschluss is submitted by hand, which is its Feststellung, and
  cancelled and amended when it changes. A Berichtigung that is filed, and the amendment of a cancelled
  Jahresabschluss, replace the filings of their key.
- A document that goes to ELSTER keeps all but its remarks after an accepted Senden or one whose outcome is unknown
  (Transmittable.refuse_changes_after_sending).

The hooks a module implements, its fields and the API are listed in docs/jahresmeldungen.md.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, escape_html, getdate

from steuerbote.jahresmeldung import findings, lifecycle, overrides
from steuerbote.jahresmeldung.findings import Finding, Severity
from steuerbote.jahresmeldung.lifecycle import (
	FILING,
	Event,
	Lifecycle,
	LifecycleError,
	Other,
	Problem,
	Status,
)
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import (
	EXTERN,
	MEIN_ELSTER,
	OTHER_WAY,
	SUCCEEDED,
)
from steuerbote.steuerbote.doctype.elster_transmission.transmission import (
	TRANSMISSION,
	Transmittable,
	filings,
)
from steuerbote.steuerbote.doctype.vat_return.vat_return import TRANSFERTICKET

FINDINGS_TABLE = "findings"
FILING_FIELDS = ("filed_via", "filed_on", "transferticket", "filing_note", "filed_by")
# Set when the document is made, by Berichtigung anlegen or the API; every later save keeps them.
INSERT_ONLY_FIELDS = ("is_correction", "corrects")
FILED_THROUGH_ERIC = "eric"
RECALCULATE = "SB-NEU-BERECHNEN"


@dataclass(frozen=True)
class Calculation:
	"""What Berechnen of a module found: the lines it computed, with the columns of its LINE_COLUMNS, the rows of its
	other tables, the values of its fields, its findings, and whether the checks it reports besides passed."""

	lines: Sequence[Mapping[str, Any]] = ()
	tables: Mapping[str, Sequence[Mapping[str, Any]]] = field(default_factory=dict)
	values: Mapping[str, Any] = field(default_factory=dict)
	findings: Sequence[Finding] = ()
	passed: bool = True


class AnnualFiling:
	"""An annual document; see the module docstring and docs/jahresmeldungen.md for the hooks and the fields."""

	LIFECYCLE: Lifecycle = FILING
	KEY_FIELDS: tuple[str, ...] = ("company", "year")
	LINES: str | None = None
	LINE_COLUMNS: overrides.Columns = overrides.Columns()
	CALCULATED_TABLES: tuple[str, ...] = ()
	CALCULATED_FIELDS: tuple[str, ...] = ()
	FILED_OUTSIDE: tuple[str, ...] = (MEIN_ELSTER, OTHER_WAY)

	# The hooks of a module.

	def compute(self) -> Calculation:
		"""Berechnen of the module: read the sources and run its core."""
		raise NotImplementedError(f"{self.doctype} computes nothing")

	def check_reported(self, lines: Sequence[Mapping[str, Any]]) -> Sequence[Finding]:
		"""The findings on the lines as filed, after Berechnen kept the corrections and the lines by hand."""
		return ()

	def compute_deadline(self) -> date | None:
		"""The Fälligkeitsdatum of the document; None until the module names it."""
		return None

	def set_amounts(self) -> None:
		"""Set the fields the module derives from the lines as filed, such as its sums, on every save."""

	def amounts_kept(self, stored: Document) -> bool:
		"""Whether ``stored`` holds the fields set_amounts derives from the lines of this document."""
		return True

	def check_filing(self) -> None:
		"""Refuse a filing the module does not allow, beyond Bereit oder Anmerkungen."""

	def correction_values(self) -> dict[str, Any]:
		"""The values a Berichtigung of this document starts with, beyond its key and its lines."""
		return {}

	# Frappe.

	@property
	def transmits(self) -> bool:
		"""Whether the document goes to ELSTER through ERiC."""
		return isinstance(self, Transmittable)

	def onload(self) -> None:
		if self.transmits:
			self.set_onload("elster", self.elster_state())
			self.set_onload("elster_run", self.latest_run())
		self.set_onload("annual_filing", self.annual_state())

	def annual_state(self) -> dict[str, Any]:
		"""For the form: the statuses of a calculated and of a filed document, the ways a note of a filing names, and
		whether a Berichtigung can be made from the document."""
		return {
			"calculated": list(self.LIFECYCLE.calculated),
			"filings": list(self.LIFECYCLE.filings),
			"filed_outside": list(self.FILED_OUTSIDE) if self.transmits else [],
			"submitted_by_hand": self.LIFECYCLE.submitted_by_hand,
			"can_correct": self.docstatus == 1 and self.status in self.LIFECYCLE.filings,
		}

	def before_insert(self) -> None:
		"""A new document starts as a draft that Berechnen has not read and nobody filed, whatever it was made with: it
		keeps its corrections and lines by hand, and nothing of a calculation."""
		for table in (*self.CALCULATED_TABLES, FINDINGS_TABLE):
			self.set(table, [])
		if self.LINES:
			kept = self._lines(overrides.recalculated, (), _rows(self.get(self.LINES)), self.LINE_COLUMNS)
			self.set(self.LINES, kept)
		self.update(
			{
				"status": Status.DRAFT,
				"ready": 0,
				**dict.fromkeys(self.CALCULATED_FIELDS),
				**dict.fromkeys(FILING_FIELDS),
			}
		)

	def validate(self) -> None:
		if self.transmits:
			self.refuse_changes_while_transmitting()
			self.refuse_changes_after_sending(FILING_FIELDS if self.flags.filed_outside else ())
		if any(not self.get(fieldname) for fieldname in self.KEY_FIELDS):
			return  # the mandatory check that follows names the missing fields
		self._keep_insert_only_fields()
		self.set_period()
		self._check_correction()
		self._refuse_second_document()
		self._keep_the_filing()
		self._keep_the_calculation()
		self._set_reported()
		self.set_amounts()

	def before_submit(self) -> None:
		"""An Erklärung and the E-Bilanz are filed by a Senden that ELSTER accepted, with what came back, or by the note of
		their filing; a Jahresabschluss by hand, which is its Feststellung."""
		sent = None
		if not self.LIFECYCLE.submitted_by_hand:
			sent = None if self.flags.filed_outside or not self.transmits else self.accepted_send()
			if not (self.flags.filed_outside or sent):
				frappe.throw(
					_(
						"{0} is filed through Senden or by noting its filing in Mein ELSTER or outside Steuerbote, not by Buchen alone."
					).format(self.name)
				)
		self.check_fit_for_filing()
		self.require_amounts_as_stored(self.get_doc_before_save() or self)
		if sent:
			self.update(
				{
					"filed_via": FILED_THROUGH_ERIC,
					"filed_on": getdate(sent.finished_at),
					"transferticket": sent.transferticket,
					"filing_note": None,
					"filed_by": frappe.db.get_value(TRANSMISSION, sent.name, "user"),
				}
			)
		self.status = self._move(Event.FILE)

	def on_submit(self) -> None:
		"""A Berichtigung replaces the filings of its key, and an amendment the cancelled document it amends."""
		filed_statuses = [str(status) for status in self.LIFECYCLE.filings]
		replaced = (
			self._others(docstatus=1, status=["in", filed_statuses]) if cint(self.is_correction) else []
		)
		if self.get("amended_from"):
			replaced.append(self.amended_from)
		for name in replaced:
			frappe.get_doc(self.doctype, name).db_set("status", Status.REPLACED)

	def before_cancel(self) -> None:
		if not self.LIFECYCLE.cancellable:
			frappe.throw(
				_(
					"{0} is filed and cannot be cancelled. A change goes to the Finanzamt as a Berichtigung of it."
				).format(self.name)
			)

	@frappe.whitelist(methods=["POST"])
	def calculate(self) -> None:
		"""Berechnen: compute the document through its module and save it, with the corrections and the lines by hand it
		held."""
		self.check_permission("write")
		if self.docstatus != 0:
			frappe.throw(_("{0} is no draft and cannot be calculated.").format(self.name))
		if self.transmits:
			self.refuse_changes_while_transmitting()
			self.refuse_if_sent()
		self.set_period()
		calculation = self.compute()
		lines: list[dict[str, Any]] = []
		if self.LINES:
			lines = self._lines(
				overrides.recalculated, calculation.lines, _rows(self.get(self.LINES)), self.LINE_COLUMNS
			)
			self.set(self.LINES, lines)
		for table, rows in calculation.tables.items():
			self.set(table, [dict(row) for row in rows])
		self.update(dict(calculation.values))
		found = (*calculation.findings, *self.check_reported(lines))
		self.set(FINDINGS_TABLE, findings.rows(found))
		ready = findings.ready(found, calculation.passed)
		self.ready = int(ready)
		self.status = self._move(Event.CALCULATE, ready=ready)
		self.flags.calculating = True
		try:
			self.save()
		finally:
			self.flags.calculating = False

	@frappe.whitelist(methods=["POST"])
	def make_correction(self) -> str:
		"""Berichtigung anlegen: a new document of the key that corrects this filed one, with its corrections and lines by
		hand, calculated at once. Returns its name."""
		frappe.has_permission(self.doctype, "create", throw=True)
		if self.docstatus != 1 or self.status not in self.LIFECYCLE.filings:
			frappe.throw(_("A Berichtigung is made from a filed document."))
		drafts = self._others(docstatus=0)
		if drafts:
			frappe.throw(
				_("{0} is a draft for the same company and year already. File it or delete it first.").format(
					drafts[0]
				)
			)
		lines = {}
		if self.LINES:
			lines = {
				self.LINES: self._lines(
					overrides.recalculated, (), _rows(self.get(self.LINES)), self.LINE_COLUMNS
				)
			}
		correction = frappe.get_doc(
			{
				"doctype": self.doctype,
				**{fieldname: self.get(fieldname) for fieldname in self.KEY_FIELDS},
				"is_correction": 1,
				"corrects": self.name,
				**lines,
				**self.correction_values(),
			}
		).insert()
		correction.calculate()
		return correction.name

	@frappe.whitelist(methods=["POST"])
	def mark_filed_outside(
		self,
		filed_via: str = OTHER_WAY,
		note: str | None = None,
		transferticket: str | None = None,
		filed_on: str | None = None,
	) -> str:
		"""In Mein ELSTER abgegeben, or Als außerhalb abgegeben vermerken: the document went to the Finanzamt another way.
		Submits it with how, when and by whom the filing was noted, and returns the name of the ELSTER Transmission
		that records it."""
		self.check_permission("submit")
		if not self.transmits:
			frappe.throw(_("{0} does not go to the Finanzamt.").format(self.name))
		note = (note or "").strip()
		ticket = (transferticket or "").strip()
		if filed_via not in self.FILED_OUTSIDE:
			frappe.throw(_("Steuerbote knows no way of filing {0}.").format(escape_html(str(filed_via))))
		if filed_via == OTHER_WAY and not note:
			frappe.throw(_("Note how and when {0} was filed.").format(self.name))
		if ticket and not TRANSFERTICKET.fullmatch(ticket):
			frappe.throw(
				_(
					"{0} is no Transferticket: it has 32 characters, as the protocol of ELSTER shows it."
				).format(escape_html(ticket))
			)
		filed_date = getdate(filed_on) if filed_on else getdate()
		if filed_date > getdate():
			frappe.throw(_("A return cannot be filed in the future."))
		self.lock_for_transmission()
		if self.docstatus != 0:
			frappe.throw(_("{0} is no draft and cannot be marked as filed.").format(self.name))
		accepted = self.accepted_send()
		if accepted:
			frappe.throw(
				_(
					"ELSTER accepted {0} with Transferticket {1}, so it was not filed outside Steuerbote: submit it with Buchen."
				).format(self.name, accepted.transferticket)
			)
		self.refuse_second_filing()
		self.update(
			{
				"filed_via": filed_via,
				"filed_on": filed_date,
				"transferticket": ticket or None,
				"filing_note": note or None,
				"filed_by": frappe.session.user,
			}
		)
		self.flags.filed_outside = True
		try:
			self.submit()
		finally:
			self.flags.filed_outside = False
		return self.new_transmission(
			EXTERN,
			simulated=False,
			status=SUCCEEDED,
			remarks=note or None,
			filed_via=filed_via,
			transferticket=ticket or None,
			filed_on=filed_date,
		).name

	# What a module calls.

	def set_period(self) -> None:
		"""Geschäftsjahr, Von-Datum and Bis-Datum: the Fiscal Year of the company that ends in the year of the document,
		whose year is the VZ, the EZ or the year the Wirtschaftsjahr ends in; and the Fälligkeitsdatum of the module."""
		fiscal_year = fiscal_year_ending_in(self.company, cint(self.year))
		self.update(
			{
				"fiscal_year": fiscal_year.name,
				"from_date": fiscal_year.year_start_date,
				"to_date": fiscal_year.year_end_date,
				"deadline": self.compute_deadline(),
			}
		)

	def check_fit_for_filing(self) -> None:
		"""Bereit oder Anmerkungen: a calculated document that is ready, or explained in its remarks; then the checks of
		the module."""
		try:
			lifecycle.fit_for_filing(self.LIFECYCLE, self.status, bool(cint(self.ready)), self.remarks)
		except LifecycleError as error:
			self._refuse(error)
		self.check_filing()

	def require_amounts_as_stored(self, stored: Document) -> None:
		"""A filing carries the amounts the document holds, which every save sets from its lines: computed again from the
		lines, they are those ``stored`` holds, or nothing is filed."""
		lines_kept = not self.LINES or overrides.kept(
			[row.as_dict() for row in self.get(self.LINES)],
			[row.as_dict() for row in stored.get(self.LINES)],
			self.LINE_COLUMNS,
		)
		if not (lines_kept and self.amounts_kept(stored)):
			frappe.throw(
				_(
					"The amounts of {0} do not agree with its lines as stored. Reload it, and calculate it again if they still do not agree."
				).format(self.name)
			)

	def refuse_second_filing(self) -> None:
		"""A key is filed once, also through a Senden of another document of it, cancelled or not: every further
		document of it is a Berichtigung."""
		try:
			lifecycle.refuse_second_filing(bool(cint(self.is_correction)), self._other_documents())
		except LifecycleError as error:
			self._refuse(error)

	def _keep_insert_only_fields(self) -> None:
		before = self.get_doc_before_save()
		if before is not None:
			self.update({fieldname: before.get(fieldname) for fieldname in INSERT_ONLY_FIELDS})

	def _check_correction(self) -> None:
		"""A Berichtigung corrects a filed document of its key."""
		if not cint(self.is_correction):
			self.corrects = None
			return
		corrected = (
			frappe.db.get_value(
				self.doctype, self.corrects, ["name", "docstatus", *self.KEY_FIELDS], as_dict=True
			)
			if self.corrects
			else None
		)
		other = (
			Other(corrected.name, cint(corrected.docstatus))
			if corrected and self._key_of(corrected) == self._key_of(self)
			else None
		)
		try:
			lifecycle.check_correction(True, other)
		except LifecycleError as error:
			self._refuse(error)

	def _refuse_second_document(self) -> None:
		"""A key holds one draft at a time, and a filed key takes a Berichtigung only."""
		others = self._other_documents()
		try:
			if self.is_new():
				lifecycle.refuse_second_draft(others)
			lifecycle.refuse_second_filing(bool(cint(self.is_correction)), others)
		except LifecycleError as error:
			self._refuse(error)

	def _keep_the_filing(self) -> None:
		"""Only the note of a filing sets the filing on a save, and a Senden ELSTER accepted sets it when it submits the
		document (before_submit); every other save keeps it as stored."""
		before = self.get_doc_before_save()
		if before is not None and not self.flags.filed_outside:
			self.update({fieldname: before.get(fieldname) for fieldname in FILING_FIELDS})

	def _keep_the_calculation(self) -> None:
		"""A save keeps what Berechnen stored, and takes from the lines what the company enters on them. Another key
		discards the calculation; a save that changes what a line reports leaves the document Berechnet, with a finding
		that asks for Berechnen."""
		before = self.get_doc_before_save()
		if before is None or self.flags.calculating:
			return
		if self._key_of(before) != self._key_of(self):
			for table in (*self.CALCULATED_TABLES, FINDINGS_TABLE, *((self.LINES,) if self.LINES else ())):
				self.set(table, [])
			self.update({"ready": 0, **dict.fromkeys(self.CALCULATED_FIELDS)})
			self.status = self._move(Event.DISCARD, status=before.status)
			return
		self.update(
			{fieldname: before.get(fieldname) for fieldname in ("status", "ready", *self.CALCULATED_FIELDS)}
		)
		for table in (*self.CALCULATED_TABLES, FINDINGS_TABLE):
			self.set(table, _rows(before.get(table)))
		if not self.LINES:
			return
		columns = self.LINE_COLUMNS
		stored = [row.as_dict() for row in before.get(self.LINES)]
		kept = self._lines(
			overrides.restored, stored, [row.as_dict() for row in self.get(self.LINES)], columns
		)
		for row, values in zip(self.get(self.LINES), kept, strict=True):
			row.update(
				{column: values[column] for column in (*columns.filled, columns.manual, columns.reported)}
			)
		if self.status in self.LIFECYCLE.calculated and self._lines(overrides.changed, stored, kept, columns):
			self.status = self._move(Event.CHANGE)
			self.ready = 0
			stored_findings = findings.of_rows(_rows(before.get(FINDINGS_TABLE)))
			recalculate = Finding(
				RECALCULATE,
				Severity.ERROR,
				_(
					"A correction or a line by hand changed since Berechnen. Calculate again: Berechnen checks the document with them and keeps them."
				),
			)
			self.set(FINDINGS_TABLE, findings.rows((*stored_findings, recalculate)))

	def _set_reported(self) -> None:
		if not self.LINES:
			return
		columns = self.LINE_COLUMNS
		for row in self.get(self.LINES):
			row.set(columns.reported, self._lines(overrides.reported, row.as_dict(), columns))

	# Helpers.

	def _key_of(self, doc: Mapping[str, Any] | Document) -> tuple:
		return tuple(cstr(doc.get(fieldname)) for fieldname in self.KEY_FIELDS)

	def _others(self, **filters: Any) -> list[str]:
		"""The other documents of the key, the latest first."""
		return frappe.get_all(
			self.doctype,
			filters={
				**{fieldname: self.get(fieldname) for fieldname in self.KEY_FIELDS},
				"name": ["!=", self.name or ""],
				**filters,
			},
			order_by="creation desc",
			pluck="name",
		)

	def _other_documents(self) -> list[Other]:
		"""The other documents of the key with their docstatus, whether they are a Berichtigung and whether they were sent
		through Steuerbote, accepted or with an outcome that is unknown."""
		rows = frappe.get_all(
			self.doctype,
			filters={
				**{fieldname: self.get(fieldname) for fieldname in self.KEY_FIELDS},
				"name": ["!=", self.name or ""],
			},
			fields=["name", "docstatus", "is_correction"],
			order_by="creation desc",
		)
		sent = (
			{row.document for row in filings(self.doctype, [row.name for row in rows])}
			if self.transmits
			else set()
		)
		return [
			Other(row.name, cint(row.docstatus), bool(cint(row.is_correction)), row.name in sent)
			for row in rows
		]

	def _move(self, event: Event, *, ready: bool = False, status: str | None = None) -> Status:
		try:
			return self.LIFECYCLE.move(status or self.status, event, ready=ready)
		except LifecycleError as error:
			self._refuse(error)

	def _refuse(self, error: LifecycleError) -> None:
		messages = {
			Problem.NO_MOVE: _("{0} cannot change from {1} this way.").format(self.name, _(error.subject)),
			Problem.NOT_CALCULATED: _("Calculate {0} before filing it.").format(self.name),
			Problem.NOT_READY: _(
				"{0} is not ready: an error of its findings holds it. Explain in the remarks why it is filed nonetheless."
			).format(self.name),
			Problem.DRAFT_EXISTS: _(
				"{0} is a draft for the same company and year already. File it or delete it first."
			).format(error.subject),
			Problem.FILED_EXISTS: _(
				"{0} is filed already for the same company and year. Make a Berichtigung of it with Make Berichtigung."
			).format(error.subject),
			Problem.NOT_A_FILING: _(
				"A Berichtigung corrects a filed document for the same company and year; make it there with Make Berichtigung."
			),
		}
		frappe.throw(messages[error.problem])

	def _lines(self, read: Callable[..., Any], *args: Any) -> Any:
		"""Call a reader of the lines and turn a line it refuses into a message for the user."""
		try:
			return read(*args)
		except overrides.OverrideError as error:
			key = escape_html(error.key)
			messages = {
				overrides.Problem.NO_KEY: _("A line of {0} names nothing it reports.").format(self.name),
				overrides.Problem.DUPLICATE: _("The line {0} is listed twice.").format(key),
				overrides.Problem.MISSING_REASON: _(
					"The line {0}: a correction or a line by hand needs a reason."
				).format(key),
				overrides.Problem.REMOVED: _(
					"The line {0} comes from Berechnen and stays on the document; a correction with a reason files another amount."
				).format(key),
			}
			frappe.throw(messages[error.problem])


def fiscal_year_ending_in(company: str, year: int) -> frappe._dict:
	"""The Fiscal Year of the company that ends in the year: one that names the company, or one that names none and so
	serves every company, as ERPNext reads them (Fiscal Year Company)."""
	ending = frappe.get_all(
		"Fiscal Year",
		filters={"disabled": 0, "year_end_date": ["between", (date(year, 1, 1), date(year, 12, 31))]},
		fields=["name", "year_start_date", "year_end_date"],
		order_by="year_end_date desc",
	)
	serving = [fiscal_year for fiscal_year in ending if _serves(fiscal_year.name, company)]
	if len(serving) != 1:
		frappe.throw(
			_("{0} needs exactly one Fiscal Year that ends in {1}, not {2}.").format(
				escape_html(company), year, len(serving)
			)
		)
	return serving[0]


def _serves(fiscal_year: str, company: str) -> bool:
	companies = [row.company for row in frappe.get_cached_doc("Fiscal Year", fiscal_year).companies]
	return not companies or company in companies


def _rows(rows) -> list[dict[str, Any]]:
	"""Rows of a table as they were stored, for a save to write them again."""
	return [row.as_dict(no_default_fields=True, no_child_table_fields=True) for row in rows or ()]
