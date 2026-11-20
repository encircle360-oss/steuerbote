"""Recapitulative Statement: the Zusammenfassende Meldung of one company for one Meldezeitraum.

"Berechnen" (calculate) takes the Meldezeitraum from the rhythm of the ZM in the VAT Return Settings, reads what
each voucher adds to Kz 41, 42 and 21 in its months through steuerbote.zm_sources, and leaves every line, amount
and rule to the core in steuerbote.zm: the lines per USt-IdNr. and Art (lines.build), the threshold of
50,000 euros (rhythm.threshold_findings), the reconciliation with the ledger and the filed Voranmeldungen
(reconciliation.reconcile) and the previous Meldezeitraum (comparison). bridge.py maps the results onto the
tables. Every save rebuilds the lines from the rows of vouchers and lines, so an override with a Begründung
lifts the block of its line at once; the threshold and the reconciliation with the ledger hold the statement
back until "Berechnen" finds them gone.

"USt-IdNrn. prüfen" (confirm_vat_ids) asks the BZSt about each USt-IdNr. the lines report, in a background job,
one query after the other and none repeated (steuerbote.vatid), and keeps every query as a VAT ID Confirmation.
A number holds the statement back until its latest confirmation says it is valid, or its line is overridden
with a Begründung (decision of the maintainer). "CSV für Mein ELSTER" (make_csv_file) writes the lines into the
file that the form of Mein ELSTER imports (steuerbote.zm.csv_file). "Berichtigung anlegen" (make_correction)
starts a statement for the same Meldezeitraum that reports only what changed against the filings
(steuerbote.zm.correction). "In Mein ELSTER abgegeben" and "Als außerhalb abgegeben vermerken"
(mark_filed_outside) submit the statement with a note of the filing; Buchen alone files nothing, and a filed
statement cannot be cancelled, since a change goes to the BZSt as a Berichtigung.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

import frappe
from frappe import _
from frappe.core.doctype.file.utils import get_content_hash
from frappe.model.document import Document
from frappe.utils import cint, escape_html, getdate, strip_html
from frappe.utils.background_jobs import is_job_enqueued

from steuerbote import holiday_list, vatid, zm_sources
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import FILED_VIA, OTHER_WAY
from steuerbote.steuerbote.doctype.recapitulative_statement import bridge
from steuerbote.steuerbote.doctype.vat_id_confirmation import vat_id_confirmation
from steuerbote.steuerbote.doctype.vat_return.vat_return import (
	TRANSFERTICKET,
	SiteFigures,
	mapping_for,
	settings_for,
)
from steuerbote.steuerbote.report.ustva_kennzahlen.comparison import Thresholds
from steuerbote.vatid import UrllibFetch
from steuerbote.zm.comparison import compare, comparison_hints
from steuerbote.zm.correction import as_filed
from steuerbote.zm.csv_file import csv_file
from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Finding
from steuerbote.zm.lines import Art, Statement, build
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.reconciliation import Filed, ledger_changes, reconcile
from steuerbote.zm.rhythm import Coverage, Rule, check_notices, coverage, threshold_findings, threshold_window

DOCTYPE = "Recapitulative Statement"

DRAFT = "Entwurf"
CALCULATED = "Berechnet"
READY = "Bereit"
FILED = "Abgegeben"
REPLACED = "Ersetzt"

PERIOD_FIELDS = ("company", "year", "period_kind", "period_index")
CALCULATED_TABLES = ("lines", "vouchers", "reconciliation", "comparison", "hints")
TOTALS = ("total_l", "total_d", "total_s")

LOCK_FIELD = "confirmation_in_progress"
CONFIRMATION_JOB = (
	"steuerbote.steuerbote.doctype.recapitulative_statement.recapitulative_statement.run_confirmation"
)
CONFIRMATION_EVENT = "steuerbote_vat_id_confirmation"
# A confirmation asks at most three times, the simple and the qualified query and VIES, and UrllibFetch waits
# up to a minute for each answer.
SECONDS_PER_NUMBER = 200
MINIMUM_TIMEOUT = 300


class RecapitulativeStatement(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.recapitulative_statement_comparison.recapitulative_statement_comparison import (
			RecapitulativeStatementComparison,
		)
		from steuerbote.steuerbote.doctype.recapitulative_statement_hint.recapitulative_statement_hint import (
			RecapitulativeStatementHint,
		)
		from steuerbote.steuerbote.doctype.recapitulative_statement_line.recapitulative_statement_line import (
			RecapitulativeStatementLine,
		)
		from steuerbote.steuerbote.doctype.recapitulative_statement_reconciliation.recapitulative_statement_reconciliation import (
			RecapitulativeStatementReconciliation,
		)
		from steuerbote.steuerbote.doctype.recapitulative_statement_voucher.recapitulative_statement_voucher import (
			RecapitulativeStatementVoucher,
		)

		amended_from: DF.Link | None
		anzeige: DF.Check
		company: DF.Link
		comparison: DF.Table[RecapitulativeStatementComparison]
		confirmation_in_progress: DF.Check
		corrects: DF.Link | None
		deadline: DF.Date | None
		filed_by: DF.Link | None
		filed_on: DF.Date | None
		filed_via: DF.Literal["", "mein_elster", "other_way"]
		filing_note: DF.SmallText | None
		from_date: DF.Date | None
		goods_from: DF.Date | None
		goods_to: DF.Date | None
		hints: DF.Table[RecapitulativeStatementHint]
		lines: DF.Table[RecapitulativeStatementLine]
		meldeart: DF.Literal["Erstmeldung", "Berichtigung"]
		naming_series: DF.Literal["ZM-.YYYY.-.#####"]
		period_index: DF.Int
		period_kind: DF.Literal["month", "two_months", "quarter", "year"]
		period_label: DF.Data | None
		quart: DF.Int
		ready: DF.Check
		reconciliation: DF.Table[RecapitulativeStatementReconciliation]
		remarks: DF.SmallText | None
		services_from: DF.Date | None
		services_to: DF.Date | None
		status: DF.Literal["Entwurf", "Berechnet", "Bereit", "Abgegeben", "Ersetzt"]
		to_date: DF.Date | None
		total_d: DF.Currency
		total_l: DF.Currency
		total_s: DF.Currency
		transferticket: DF.Data | None
		vouchers: DF.Table[RecapitulativeStatementVoucher]
		widerruf: DF.Check
		year: DF.Int
	# end: auto-generated types

	def onload(self) -> None:
		"""Tell the form whether the lock of a confirmation is stale, so that it releases it."""
		draft = self.docstatus == 0 and not self.is_new()
		self.set_onload("confirmation", {"stale": draft and self._has_stale_confirmation()})

	def validate(self) -> None:
		self._refuse_changes_while_confirming()
		if self._lacks_mandatory_values():
			return  # the mandatory check that follows names the missing fields
		covered = self._set_period()
		period = covered.period
		self._check_correction()
		self._refuse_second_statement(covered)
		self._discard_calculation_of_another_period()
		with zm_errors():
			check_notices(period, bool(cint(self.anzeige)), bool(cint(self.widerruf)))
		if not self.flags.calculating:
			self._apply_lines(period)

	def before_submit(self) -> None:
		if not self.flags.filed_outside:
			frappe.throw(
				_(
					"A Zusammenfassende Meldung is filed by noting its filing in Mein ELSTER or outside Steuerbote, not by Buchen alone."
				)
			)
		self._check_fit_for_filing()
		self.status = FILED

	def before_cancel(self) -> None:
		frappe.throw(
			_(
				"{0} is filed with the BZSt and cannot be cancelled. A change goes to the BZSt as a Berichtigung."
			).format(self.name)
		)

	def on_submit(self) -> None:
		if self.meldeart == bridge.BERICHTIGUNG:
			for name in self._other_filings(status=FILED):
				frappe.get_doc(DOCTYPE, name).db_set("status", REPLACED)

	@frappe.whitelist(methods=["POST"])
	def calculate(self) -> None:
		"""Berechnen: the lines of the Meldezeitraum from the ledger, with their vouchers and the latest
		confirmation of each USt-IdNr., the threshold, the reconciliation and the previous period; overrides
		with a Begründung stay."""
		frappe.has_permission(DOCTYPE, "write", self, throw=True)
		if self.docstatus != 0:
			frappe.throw(_("Only a draft Zusammenfassende Meldung can be calculated."))
		self._refuse_changes_while_confirming()
		covered = self._set_period()
		period = covered.period
		settings = settings_for(self.company)
		rules = settings.get_zm_rules()
		mapping = mapping_for(self.company, cint(self.year))
		figures = self._figures()
		with zm_errors():
			overrides = bridge.overrides_of(self.lines)
			shares = zm_sources.shares(self.company, covered, mapping)
			previous_period = period.previous()
			previous_shares = zm_sources.shares(
				self.company, _coverage_or_months(rules, previous_period), mapping
			)
			parties = zm_sources.parties(item.voucher for item in (*shares, *previous_shares))
			amounts = bridge.voucher_amounts_of(shares, parties)
			vat_ids = bridge.line_vat_ids(amounts, overrides)
			latest = vat_id_confirmation.latest(self.company, vat_ids)
			outcomes = {vat_id: record.result for vat_id, record in latest.items()}
			statement = build(amounts, figures, bridge.validity_for(vat_ids, outcomes), overrides)
			previous = build(bridge.voucher_amounts_of(previous_shares, parties), figures)
			compared = compare(statement, previous, _thresholds(settings).exceeded)
			deliveries = zm_sources.deliveries(self.company, threshold_window(period), mapping)
			threshold = threshold_findings(rules, period, deliveries, figures)
			reconciliation = reconcile(statement, shares, figures, self._filed(covered))
			held = self._held() if self.meldeart == bridge.BERICHTIGUNG else None
			confirmations = {vat_id: bridge.confirmation_fields(record) for vat_id, record in latest.items()}
			lines = bridge.line_rows(statement, confirmations, period, held)
		self.set("lines", lines)
		self.set("vouchers", bridge.voucher_rows(amounts, parties))
		self.set("reconciliation", bridge.reconciliation_rows(reconciliation))
		self.set("comparison", bridge.comparison_rows(compared))
		findings = [
			*statement.findings,
			*threshold,
			*reconciliation.findings,
			*comparison_hints(compared, previous_period, figures),
		]
		self.set("hints", bridge.hint_rows(findings))
		self._set_totals_and_status(statement)
		self.flags.calculating = True
		try:
			self.save()
		finally:
			self.flags.calculating = False

	@frappe.whitelist(methods=["POST"])
	def confirm_vat_ids(self) -> int:
		"""USt-IdNrn. prüfen: ask about each USt-IdNr. the lines report, in a background job; returns how many
		numbers the job asks about."""
		self.check_permission("write")
		self._lock()
		if self.docstatus != 0:
			frappe.throw(_("Only the USt-IdNrn. of a draft Zusammenfassende Meldung are confirmed."))
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the statement before confirming its USt-IdNrn."))
		self._close_stale_confirmation()
		requester(self.company)
		numbers = bridge.numbers_to_confirm(self.lines)
		if not numbers:
			frappe.throw(_("The statement reports no USt-IdNr. to confirm."))
		self.db_set(LOCK_FIELD, 1)
		frappe.enqueue(
			CONFIRMATION_JOB,
			queue="long",
			timeout=max(MINIMUM_TIMEOUT, SECONDS_PER_NUMBER * len(numbers)),
			job_id=confirmation_job_id(self.name),
			enqueue_after_commit=True,
			name=self.name,
		)
		return len(numbers)

	@frappe.whitelist(methods=["POST"])
	def release_stale_confirmation(self) -> None:
		"""Lift the lock of a confirmation whose background job is gone; the form calls this when it finds one.
		What the job stored before it stopped stays, and Berechnen or another confirmation shows it."""
		self.check_permission("write")
		self._lock()
		self._close_stale_confirmation()

	@frappe.whitelist(methods=["POST"])
	def make_csv_file(self) -> str:
		"""CSV für Mein ELSTER: the statement as saved, as the file the form of Mein ELSTER imports, attached
		privately; a Berichtigung writes the lines that change what was filed. Returns the address of the file."""
		saved = frappe.get_doc(self.doctype, self.name)
		saved._require_csv_file()
		period = saved._chosen_period()
		with zm_errors():
			rows, correction = saved._file_lines(period)
			content = csv_file(rows, correction=correction)
		return saved._attach(bridge.csv_file_name(period, correction), content)

	@frappe.whitelist(methods=["POST"])
	def make_correction(self) -> str:
		"""Berichtigung anlegen: a new statement for the Meldezeitraum, with the overrides of this one, that
		reports what changed against the filings; calculated at once. Returns its name."""
		frappe.has_permission(DOCTYPE, "create", throw=True)
		if self.docstatus != 1 or self.status != FILED:
			frappe.throw(
				_("A Berichtigung is made from the latest filed Zusammenfassende Meldung of its period.")
			)
		drafts = frappe.get_all(DOCTYPE, filters={**self._period_filters(), "docstatus": 0}, pluck="name")
		if drafts:
			frappe.throw(
				_("{0} is a draft for {1} already. File it or delete it first.").format(
					drafts[0], self.period_label
				)
			)
		changes = self._changes_since_filing()
		correction = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"company": self.company,
				"year": self.year,
				"period_kind": self.period_kind,
				"period_index": self.period_index,
				"meldeart": bridge.BERICHTIGUNG,
				"corrects": self.name,
				"lines": [
					{name: row.get(name) for name in ("vat_id", "art", "override", "override_reason")}
					for row in self.lines
					if (row.override_reason or "").strip()
				],
			}
		).insert()
		correction.calculate()
		if changes:
			frappe.msgprint(
				"<br>".join(
					(
						_(
							"The ledger of {0} has changed since {1} was filed. The Berichtigung takes in these changes:"
						).format(self.period_label, self.name),
						*(escape_html(finding.text) for finding in changes),
					)
				),
				title=_("Make Berichtigung"),
			)
		return correction.name

	@frappe.whitelist(methods=["POST"])
	def ledger_changes_since_filing(self) -> list[str]:
		"""The form asks this when it shows the filing of a Meldezeitraum: the vouchers whose share in the ledger of
		its months now differs from the one it filed, as sentences, none while the ledger books what it filed.

		Without the immutable ledger of the Accounts Settings, a cancellation takes an invoice out of its own
		month, so that the filed month changes and no later ZM reports the cancellation, which the Anleitung zur
		ZM wants in the Meldezeitraum of the change (IV.10); a Berichtigung then reports it.
		"""
		if self.docstatus != 1 or self.status != FILED:
			return []
		return [finding.text for finding in self._changes_since_filing()]

	@frappe.whitelist(methods=["POST"])
	def mark_filed_outside(
		self,
		remarks: str | None = None,
		filed_via: str = OTHER_WAY,
		transferticket: str | None = None,
		filed_on: str | None = None,
	) -> None:
		"""In Mein ELSTER abgegeben, or Als außerhalb abgegeben vermerken: the statement went to the BZSt with
		the file for Mein ELSTER or another way. Submits it with how, when and by whom it was noted."""
		self.check_permission("submit")
		note = (remarks or "").strip()
		ticket = (transferticket or "").strip()
		if filed_via not in FILED_VIA:
			frappe.throw(_("Steuerbote knows no way of filing {0}.").format(escape_html(str(filed_via))))
		if filed_via == OTHER_WAY and not note:
			frappe.throw(_("Note how and when the statement was filed."))
		if ticket and not TRANSFERTICKET.fullmatch(ticket):
			frappe.throw(
				_(
					"{0} is no Transferticket: it has 32 characters, as the protocol of ELSTER shows it."
				).format(escape_html(ticket))
			)
		filed_date = getdate(filed_on) if filed_on else getdate()
		if filed_date > getdate():
			frappe.throw(_("A Zusammenfassende Meldung cannot be filed in the future."))
		self._lock()
		if self.docstatus != 0:
			frappe.throw(_("Only a draft Zusammenfassende Meldung can be marked as filed."))
		self._refuse_second_filing()
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

	def refresh_confirmations(self) -> None:
		"""Show on each line the latest confirmation of its USt-IdNr."""
		latest = vat_id_confirmation.latest(self.company, (row.vat_id for row in self.lines))
		for row in self.lines:
			record = latest.get(row.vat_id)
			row.update(
				bridge.confirmation_fields(record) if record else dict.fromkeys(bridge.CONFIRMATION_FIELDS)
			)

	def _lacks_mandatory_values(self) -> bool:
		return (
			not self.company
			or self.year is None
			or not self.period_kind
			or any(not row.art for row in self.lines)
		)

	def _set_period(self) -> Coverage:
		"""Meldezeitraum, code, dates and deadline, and the months whose lines the statement reports, as the rhythm
		in the settings gives them; the statement keeps the months, so that checks after its filing read them."""
		covered = self._coverage()
		period = covered.period
		self.update(
			{
				"quart": period.quart,
				"period_label": period.label,
				"from_date": period.start,
				"to_date": period.end,
				"deadline": period.deadline(holiday_list.holidays(self.company)),
				**bridge.coverage_fields(covered),
			}
		)
		return covered

	def _coverage(self) -> Coverage:
		"""The months the rhythm in the settings gives the chosen Meldezeitraum."""
		period = self._chosen_period()
		rules = settings_for(self.company).get_zm_rules()
		if not rules:
			frappe.throw(
				_(
					"The VAT Return Settings of {0} have no rhythm of the Zusammenfassende Meldung yet. Enter it before the first statement."
				).format(self.company)
			)
		with zm_errors():
			return coverage(rules, period)

	def _chosen_period(self) -> ReportingPeriod:
		try:
			return bridge.reporting_period(self.period_kind, cint(self.year), cint(self.period_index))
		except ValueError:
			frappe.throw(
				_(
					"There is no Meldezeitraum {0} of the kind {1} in {2}: months run from 1 to 12, quarters from 1 to 4."
				).format(self.period_index, _(self.period_kind), self.year)
			)

	def _period_filters(self) -> dict:
		return {"company": self.company, "year": cint(self.year), "quart": cint(self.quart)}

	def _other_filings(self, **filters) -> list[str]:
		"""The filed statements of the company and Meldezeitraum other than this one, the latest first."""
		return frappe.get_all(
			DOCTYPE,
			filters={**self._period_filters(), "docstatus": 1, "name": ["!=", self.name or ""], **filters},
			order_by="creation desc",
			pluck="name",
		)

	def _check_correction(self) -> None:
		"""A Berichtigung corrects a filed statement of its company and Meldezeitraum."""
		if self.meldeart != bridge.BERICHTIGUNG:
			self.corrects = None
			return
		corrected = (
			frappe.db.get_value(
				DOCTYPE, self.corrects, ["company", "year", "quart", "docstatus"], as_dict=True
			)
			if self.corrects
			else None
		)
		if (
			corrected is None
			or cint(corrected.docstatus) != 1
			or (corrected.company, cint(corrected.year), cint(corrected.quart))
			!= (self.company, cint(self.year), cint(self.quart))
		):
			frappe.throw(
				_(
					"A Berichtigung corrects a filed Zusammenfassende Meldung of the same company and period; make it there with Make Berichtigung."
				)
			)

	def _refuse_second_statement(self, covered: Coverage) -> None:
		"""A Meldezeitraum is filed once, and every further statement for it is a Berichtigung. The months are
		filed once as well: a change of the rules can give a month to two Meldezeiträume, such as January to the
		quarter filed before and to a monthly ZM after, so no statement reports the Lieferungen or the sonstige
		Leistungen of a month that the filing of another Meldezeitraum reported."""
		if self.meldeart != bridge.BERICHTIGUNG:
			filed = self._other_filings()
			if filed:
				frappe.throw(
					_("{0} of {1} is filed already as {2}. Make a Berichtigung of it.").format(
						self.period_label, self.company, filed[0]
					)
				)
		clash = bridge.overlapping(covered, self._filings_of_other_periods())
		if clash:
			frappe.throw(
				_(
					"{0} reports months whose Lieferungen or sonstige Leistungen {1} filed already for {2}, and a month is filed once. Check the rhythm of the Zusammenfassende Meldung in the VAT Return Settings."
				).format(self.period_label, clash.name, clash.period_label)
			)

	def _filings_of_other_periods(self) -> list[frappe._dict]:
		"""The statements that hold the current filing of another Meldezeitraum of the company in the year."""
		return frappe.get_all(
			DOCTYPE,
			filters={
				"company": self.company,
				"year": cint(self.year),
				"docstatus": 1,
				"status": FILED,
				"quart": ["!=", cint(self.quart)],
			},
			fields=["name", "period_label", "from_date", "to_date", *bridge.COVERAGE_FIELDS],
			order_by="creation asc",
		)

	def _refuse_second_filing(self) -> None:
		"""A Berichtigung reports what changed against the filings when it was made, so none may follow."""
		self._refuse_second_statement(self._coverage())
		if self.meldeart != bridge.BERICHTIGUNG:
			return
		later = frappe.get_all(
			DOCTYPE,
			filters={**self._period_filters(), "docstatus": 1, "creation": [">", self.creation]},
			pluck="name",
		)
		if later:
			frappe.throw(
				_(
					"{0} was filed for {1} after this Berichtigung was made. Make a new Berichtigung of {0}."
				).format(later[0], self.period_label)
			)

	def _discard_calculation_of_another_period(self) -> None:
		before = self.get_doc_before_save()
		if not before or self.flags.calculating:
			return
		if any(str(before.get(field)) != str(self.get(field)) for field in PERIOD_FIELDS):
			for table in CALCULATED_TABLES:
				self.set(table, [])
			self.update({"ready": 0, "status": DRAFT, **dict.fromkeys(TOTALS, 0)})

	def _apply_lines(self, period: ReportingPeriod) -> None:
		"""Rebuild the lines from the rows of vouchers and lines, so that an override lifts its block at once and
		a confirmation counts as soon as the lines show it."""
		if self.status not in (CALCULATED, READY):
			return
		with zm_errors():
			statement = bridge.statement_of(self.vouchers, self.lines, self._figures())
			held = self._held() if self.meldeart == bridge.BERICHTIGUNG else None
			rows = bridge.line_rows(statement, bridge.confirmations_of(self.lines), period, held)
		self.set("lines", rows)
		self.set("hints", bridge.merged_hints(statement, self.hints))
		self._set_totals_and_status(statement)

	def _set_totals_and_status(self, statement: Statement) -> None:
		self.update(bridge.totals(statement.meldezeilen))
		self.ready = int(bridge.ready(statement, self.hints))
		self.status = READY if self.ready else CALCULATED

	def _held(self) -> dict[tuple[str, Art], Decimal]:
		"""What the BZSt holds for the Meldezeitraum: the filings before this statement, in their order."""
		filters = {**self._period_filters(), "docstatus": 1, "name": ["!=", self.name or ""]}
		if self.docstatus == 1:
			filters["creation"] = ["<", self.creation]
		names = frappe.get_all(DOCTYPE, filters=filters, order_by="creation asc", pluck="name")
		filings = [frappe.get_doc(DOCTYPE, name) for name in names]
		with zm_errors():
			return as_filed(*(bridge.filed_meldezeilen(doc.lines) for doc in filings))

	def _filed(self, covered: Coverage) -> dict[str, Filed]:
		"""The Kz 41 and 42 of the Voranmeldungen filed for the goods months, the Kz 21 of those filed for the
		services months."""
		return {
			**bridge.filed(
				zm_sources.filed_returns(self.company, covered.goods_span),
				covered.goods_span,
				zm_sources.GOODS,
			),
			**bridge.filed(
				zm_sources.filed_returns(self.company, covered.services_span),
				covered.services_span,
				zm_sources.SERVICES,
			),
		}

	def _file_lines(self, period: ReportingPeriod) -> tuple[tuple, bool]:
		statement = bridge.statement_of(self.vouchers, self.lines, self._figures())
		held = self._held() if self.meldeart == bridge.BERICHTIGUNG else None
		return bridge.file_lines(statement, period, held)

	def _check_fit_for_filing(self) -> None:
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the statement before filing it."))
		self._require_explanation()
		covered = self._coverage()
		self._require_unchanged_ledger(covered)
		period = covered.period
		with zm_errors():
			rows, correction = self._file_lines(period)
			if correction and not rows:
				frappe.throw(
					_("The Berichtigung changes nothing that was filed for {0}.").format(self.period_label)
				)
			csv_file(rows, correction=correction)

	def _require_explanation(self) -> None:
		if not self.ready and not (self.remarks or "").strip():
			frappe.throw(
				_(
					"The statement is not ready: an error of the findings holds it. Explain in the remarks why it is filed nonetheless."
				)
			)

	def _require_csv_file(self) -> None:
		if self.docstatus == 1:
			return
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the statement before making the file for Mein ELSTER."))
		self._refuse_second_filing()
		self._require_explanation()
		self._require_unchanged_ledger(self._coverage())

	def _require_unchanged_ledger(self, covered: Coverage) -> None:
		"""Berechnen reads the ledger once: a file or a filing goes with the lines only while the ledger of their
		months still books the vouchers they were made from."""
		changes = self._ledger_changes(covered, self.vouchers)
		if changes:
			frappe.throw(
				"<br>".join(
					(
						_(
							"The ledger of {0} has changed since the statement was calculated. Calculate it again before making its file or filing it."
						).format(self.period_label),
						*(escape_html(finding.text) for finding in changes),
					)
				),
				title=_("Recapitulative Statement"),
			)

	def _changes_since_filing(self) -> tuple[Finding, ...]:
		"""What the ledger of the months the statement filed books now against the vouchers it filed."""
		period = self._chosen_period()
		covered = bridge.kept_coverage(period, self) or _coverage_or_months(
			settings_for(self.company).get_zm_rules(), period
		)
		return self._ledger_changes(covered, self.vouchers)

	def _ledger_changes(self, covered: Coverage, vouchers: Iterable[Document]) -> tuple[Finding, ...]:
		"""The vouchers whose share of Kz 41, 42 or 21 in the ledger of the months now differs from ``vouchers``,
		the rows the lines were made from: in amount, on one side only or in the USt-IdNr."""
		mapping = mapping_for(self.company, cint(self.year))
		shares = zm_sources.shares(self.company, covered, mapping)
		parties = zm_sources.parties(item.voucher for item in shares)
		with zm_errors():
			return ledger_changes(
				bridge.voucher_amounts(vouchers), bridge.voucher_amounts_of(shares, parties), self._figures()
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

	def _figures(self) -> SiteFigures:
		return SiteFigures(frappe.get_cached_value("Company", self.company, "default_currency"))

	def _lock(self) -> None:
		"""Hold the row of the statement until the request ends and read it fresh."""
		frappe.db.get_value(DOCTYPE, self.name, "name", for_update=True)
		self.reload()

	def _refuse_changes_while_confirming(self) -> None:
		"""The job writes the confirmations onto the lines, so the statement stays as it is while it runs."""
		if self.is_new() or self.flags.confirming:
			return
		if cint(frappe.db.get_value(DOCTYPE, self.name, LOCK_FIELD)):
			frappe.throw(
				_(
					"The USt-IdNrn. of this statement are being confirmed. Wait for the result before changing it."
				)
			)

	def _close_stale_confirmation(self) -> None:
		if not cint(self.confirmation_in_progress):
			return
		if is_job_enqueued(confirmation_job_id(self.name)):
			frappe.throw(_("The USt-IdNrn. of this statement are being confirmed. Wait for the result."))
		self.db_set(LOCK_FIELD, 0)

	def _has_stale_confirmation(self) -> bool:
		return bool(cint(self.confirmation_in_progress)) and not is_job_enqueued(
			confirmation_job_id(self.name)
		)


@contextmanager
def zm_errors() -> Iterator[None]:
	"""Show a broken rule of the core as a message in the language of the user."""
	try:
		yield
	except ZmError as error:
		frappe.throw(_(error.template).format(*error.values), title=_("Recapitulative Statement"))


def requester(company: str) -> str:
	"""The company's own German USt-IdNr., with which it asks the BZSt about the numbers of its customers."""
	ust_idnr = settings_for(company).ust_idnr
	if not vatid.is_german(ust_idnr):
		frappe.throw(
			_(
				"Enter the USt-IdNr. of {0} in the VAT Return Settings, DE and nine digits, before confirming USt-IdNrn."
			).format(company)
		)
	return vatid.normalize(ust_idnr)


def confirmation_job_id(name: str) -> str:
	return f"steuerbote:ustid:{name}"


def run_confirmation(name: str) -> None:
	"""Background job of RecapitulativeStatement.confirm_vat_ids: one confirmation per USt-IdNr. of the lines,
	one query after the other and none repeated.

	Each confirmation is committed as soon as it is stored: it is the proof of queries the service received,
	which nothing that fails later may take back. Then the lines show the latest confirmation of their numbers,
	the lock is released, and the user who started the job gets a realtime notice.
	"""
	user = frappe.session.user
	confirmed: list[str] = []
	failed: list[str] = []
	error_text = None
	try:
		doc = frappe.get_doc(DOCTYPE, name)
		asking = requester(doc.company)
		for vat_id in bridge.numbers_to_confirm(doc.lines):
			frappe.db.savepoint("vat_id_confirmation")
			try:
				details = zm_sources.customer_details(bridge.customer_of(doc.vouchers, vat_id))
				answer = vatid.confirm(vat_id, asking, details, UrllibFetch(), _clock)
				vat_id_confirmation.store(answer, doc.company, doc.name)
				frappe.db.commit()
				confirmed.append(vat_id)
			except Exception:
				frappe.db.rollback(save_point="vat_id_confirmation")
				frappe.log_error(title=_("Confirmation of a USt-IdNr. failed"))
				failed.append(vat_id)
		doc.reload()
		doc.refresh_confirmations()
		doc.flags.confirming = True
		doc.save()
	except Exception as error:
		frappe.db.rollback()
		error_text = _failure_text(error)
	finally:
		frappe.db.set_value(DOCTYPE, name, LOCK_FIELD, 0)
	frappe.publish_realtime(
		CONFIRMATION_EVENT,
		{"statement": name, "confirmed": len(confirmed), "failed": failed, "error": error_text},
		user=user,
		after_commit=True,
	)


def _clock() -> datetime:
	return datetime.now(UTC)


def _failure_text(error: Exception) -> str:
	"""What the user reads about a failure: the message of an expected error, else a pointer to the Error Log."""
	if isinstance(error, frappe.ValidationError | ValueError):
		return strip_html(str(error)).strip()
	frappe.log_error(title=_("Confirmation of the USt-IdNrn. failed"))
	return _("An unexpected error stopped the confirmation. The Error Log has the details.")


def _coverage_or_months(rules: list[Rule], period: ReportingPeriod) -> Coverage:
	"""The months of a Meldezeitraum to compare with: those the rules give, or all of its months where the
	rules give no ZM for it, such as before their first rule."""
	try:
		return coverage(rules, period)
	except ZmError:
		return Coverage(period, period.months, period.months)


def _thresholds(settings: Document) -> Thresholds:
	"""The thresholds of the Vorperiodenvergleich in the settings, as the report UStVA Kennzahlen reads them."""
	return Thresholds.of(
		settings.get("comparison_threshold_percent"), settings.get("comparison_threshold_amount")
	)
