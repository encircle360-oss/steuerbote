"""Recapitulative Statement: the Zusammenfassende Meldung of one company for one Meldezeitraum.

"Berechnen" (calculate) takes the Meldezeitraum from the rhythm of the ZM in the VAT Return Settings, reads what
each voucher adds to Kz 41, 42 and 21 in its months through steuerbote.zm_sources, and leaves every line, amount
and rule to the core in steuerbote.zm: the lines per USt-IdNr. and Art (lines.build), the threshold of
50,000 euros (rhythm.threshold_findings), the reconciliation with the ledger and the filed Voranmeldungen
(reconciliation.reconcile) and the earlier Meldezeiträume (comparison). bridge.py maps the results onto the
tables. Every save rebuilds the lines from the vouchers Berechnen stored, the overrides of the lines and the
latest confirmations, so an override with a Begründung lifts the block of its line at once; the threshold and
the reconciliation with the ledger hold the statement back until "Berechnen" finds them gone. Frappe keeps no
read-only field from a save through its API, so a save keeps the rest of what Berechnen stored, the status and the
filing, and a new statement starts as a draft. The file for Mein ELSTER and the filing read the ledger again and
wait for Berechnen when it books other vouchers by then; they and every transmission build the lines again from
the stored vouchers and overrides and refuse lines that differ from them.

"USt-IdNrn. prüfen" (confirm_vat_ids) asks the BZSt about each USt-IdNr. the lines report, in a background job,
one query after the other and none repeated (steuerbote.vatid), and keeps every query as a VAT ID Confirmation
(vat_id_confirmation/confirming.py).
A number holds the statement back until its latest confirmation says it is valid, or its line is overridden
with a Begründung (decision of the maintainer). "CSV für Mein ELSTER" (make_csv_file) writes the lines into the
file that the form of Mein ELSTER imports (steuerbote.zm.csv_file). "Berichtigung anlegen" (make_correction)
starts a statement for the same Meldezeitraum that reports only what changed against the filings
(steuerbote.zm.correction). "In Mein ELSTER abgegeben" and "Als außerhalb abgegeben vermerken"
(mark_filed_outside) submit the statement with a note of the filing; Buchen alone files nothing, and a filed
statement cannot be cancelled, since a change goes to the BZSt as a Berichtigung.

"Prüfen", "Testsenden" and "Senden" (transmit) run in a background job, as for every document that goes to ELSTER
through ERiC (elster_transmission/transmission.py): the job writes the statement as the Nutzdaten of the Datenart
ZMDO (nutzdaten, steuerbote.elster.zm_xml), with the Unternehmer from the VAT Return Settings, and hands them to
steuerbote.eric, through the worker of an installed runtime or the simulation; every run is recorded as an ELSTER
Transmission, and so is every note of a filing. Only a Senden that ELSTER accepted submits the statement, which
files it through ERiC with its Transferticket, and a Berichtigung filed so replaces the statements before it. Until
then a statement ELSTER accepted is filed as it was sent, and so is one whose Senden has an unknown outcome: nothing
of it changes but its remarks, and Buchen submits it, after an unknown outcome the note of its filing. A
Meldezeitraum counts as filed once a statement of it is submitted or sent through Steuerbote, accepted or with an
unknown outcome; a further statement of it is a Berichtigung.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal

import frappe
from frappe import _
from frappe.core.doctype.file.utils import get_content_hash
from frappe.model.document import Document
from frappe.utils import cint, escape_html, formatdate, getdate

from steuerbote import holiday_list, prior_filings, vatid, zm_sources
from steuerbote.elster import zm_xml
from steuerbote.eric import datenart as eric_datenart
from steuerbote.setup import start as first_year
from steuerbote.steuerbote import guards
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import (
	EXTERN,
	FILED_VIA,
	OTHER_WAY,
	SUCCEEDED,
	UNKNOWN,
)
from steuerbote.steuerbote.doctype.elster_transmission.transmission import (
	TRANSMISSION,
	Transmittable,
	filings,
)
from steuerbote.steuerbote.doctype.recapitulative_statement import bridge
from steuerbote.steuerbote.doctype.vat_id_confirmation import confirming, vat_id_confirmation
from steuerbote.steuerbote.doctype.vat_id_confirmation.confirming import Confirming
from steuerbote.steuerbote.doctype.vat_return.vat_return import (
	TRANSFERTICKET,
	SiteFigures,
	mapping_for,
	settings_for,
)
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import xml_errors
from steuerbote.steuerbote.guards import Filing
from steuerbote.steuerbote.report.ustva_kennzahlen.comparison import Thresholds
from steuerbote.vatid import Details, UrllibFetch
from steuerbote.zm.comparison import before_start, compare, comparison_hints, earlier
from steuerbote.zm.correction import as_filed
from steuerbote.zm.csv_file import csv_file
from steuerbote.zm.errors import ZmError
from steuerbote.zm.findings import Finding
from steuerbote.zm.lines import Art, Override, Statement, VoucherAmount, build
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.reconciliation import Filed, ledger_changes, reconcile
from steuerbote.zm.rhythm import (
	Coverage,
	check_notices,
	coverage,
	coverage_or_months,
	threshold_findings,
	threshold_unknown,
	threshold_window,
)

DOCTYPE = "Recapitulative Statement"

DRAFT = "Entwurf"
CALCULATED = "Berechnet"
READY = "Bereit"
FILED = "Abgegeben"
REPLACED = "Ersetzt"

# What Berechnen stores besides the lines and the hints, which every save builds anew.
STORED_TABLES = ("vouchers", "reconciliation", "comparison")
TOTALS = ("total_l", "total_d", "total_s")
# What the form lets the user enter on a line; Berechnen and every save find the rest.
LINE_INPUT = ("vat_id", "art", "override", "override_reason")
FILING_FIELDS = ("filed_via", "filed_on", "transferticket", "filing_note", "filed_by")

CONFIRMATION_JOB = (
	"steuerbote.steuerbote.doctype.recapitulative_statement.recapitulative_statement.run_confirmation"
)
# How the statement went to the BZSt when ELSTER accepted its Senden.
FILED_THROUGH_ERIC = "eric"


class RecapitulativeStatement(Filing, Confirming, Transmittable, Document):
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
		filed_via: DF.Literal["", "mein_elster", "other_way", "eric"]
		filing_note: DF.SmallText | None
		from_date: DF.Date | None
		goods_from: DF.Date | None
		goods_to: DF.Date | None
		hints: DF.Table[RecapitulativeStatementHint]
		lines: DF.Table[RecapitulativeStatementLine]
		meldeart: DF.Literal["Erstmeldung", "Berichtigung"]
		naming_series: DF.Literal["ZM-.{year}.-.#####"]
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
		transmission_in_progress: DF.Check
		vouchers: DF.Table[RecapitulativeStatementVoucher]
		widerruf: DF.Check
		year: DF.Int
	# end: auto-generated types

	def onload(self) -> None:
		"""Tell the form whether the lock of a confirmation or of a transmission is stale, so that it releases it,
		whether ERiC runs as a simulation and what the latest run of ERiC found."""
		self.set_onload("confirmation", self.confirmation_state())
		self.set_onload("elster", self.elster_state())
		self.set_onload("elster_run", self.latest_run())

	def before_insert(self) -> None:
		"""A new statement starts as a draft that Berechnen has not read and nobody filed, whatever the rows it was
		made with say: its lines keep what the form lets the user enter, the lines of its own and the overrides."""
		self.set("lines", [{field: row.get(field) for field in LINE_INPUT} for row in self.lines])
		for table in ("vouchers", "reconciliation", "comparison", "hints"):
			self.set(table, [])
		self.update({"ready": 0, "status": DRAFT, **dict.fromkeys(TOTALS, 0), **dict.fromkeys(FILING_FIELDS)})

	def validate(self) -> None:
		self.refuse_changes_while_transmitting()
		self.refuse_changes_while_confirming()
		self.refuse_changes_after_sending(FILING_FIELDS if self.flags.filed_outside else ())
		if self._lacks_mandatory_values():
			return  # the mandatory check that follows names the missing fields
		covered = self._set_period()
		period = covered.period
		self._refuse_a_period_before_the_start(period)
		self._check_correction()
		self._refuse_second_statement(covered)
		self._keep_the_filing()
		with zm_errors():
			check_notices(period, bool(cint(self.anzeige)), bool(cint(self.widerruf)))
		self._keep_the_calculation(covered)

	def before_submit(self) -> None:
		"""A statement is filed by a Senden ELSTER accepted, with what came back, or by the note of its filing,
		which files the lines the file for Mein ELSTER holds."""
		sent = None if self.flags.filed_outside else self.accepted_send()
		if not (self.flags.filed_outside or sent):
			frappe.throw(
				_(
					"A Zusammenfassende Meldung is filed through Senden or by noting its filing in Mein ELSTER or outside Steuerbote, not by Buchen alone."
				)
			)
		if sent:
			self._check_ready_to_file()
			self._require_amounts_as_stored(self.get_doc_before_save() or self)
			self.update(
				{
					"filed_via": FILED_THROUGH_ERIC,
					"filed_on": getdate(sent.finished_at),
					"transferticket": sent.transferticket,
					"filing_note": None,
					"filed_by": frappe.db.get_value(TRANSMISSION, sent.name, "user"),
				}
			)
		else:
			self._check_fit_for_filing()
			self._require_amounts_as_stored(self.get_doc_before_save() or self)
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
	@guards.on_stored("write")
	def calculate(self) -> None:
		"""Berechnen: the lines of the Meldezeitraum from the ledger, with their vouchers and the latest
		confirmation of each USt-IdNr., the threshold, the reconciliation and the previous period; overrides
		with a Begründung stay."""
		frappe.has_permission(DOCTYPE, "write", self, throw=True)
		if self.docstatus != 0:
			frappe.throw(_("Only a draft Zusammenfassende Meldung can be calculated."))
		self.refuse_changes_while_transmitting()
		self.refuse_changes_while_confirming()
		self.refuse_if_sent()
		covered = self._set_period()
		period = covered.period
		settings = settings_for(self.company)
		rules = settings.get_zm_rules()
		mapping = mapping_for(self.company, cint(self.year))
		figures = self._figures()
		with zm_errors():
			overrides = bridge.overrides_of(self.lines)
			shares = zm_sources.shares(self.company, covered, mapping)
			before = earlier(rules, covered)
			previous_shares = [
				*zm_sources.goods_shares(self.company, before.goods, mapping),
				*(
					zm_sources.services_shares(self.company, before.services, mapping)
					if before.services
					else ()
				),
			]
			parties = zm_sources.parties(item.voucher for item in (*shares, *previous_shares))
			amounts = bridge.voucher_amounts_of(shares, parties)
			statement, confirmations = self._build(amounts, overrides, covered, figures)
			previous = build(bridge.voucher_amounts_of(previous_shares, parties), figures)
			books_start = prior_filings.books_start(self.company)
			not_compared = before_start(before, books_start)
			compared = (
				()
				if not_compared
				else compare(statement, previous, _thresholds(settings).exceeded, before.arts)
			)
			window = threshold_window(period)
			deliveries = zm_sources.deliveries(self.company, window, mapping)
			prior = prior_filings.prior_filings(self.company, range(window[0].year, window[1].year + 1))
			deliveries.update(
				{
					month: amount
					for month, amount in first_year.deliveries(prior).items()
					if first_year.before_start(date(*month, 1), books_start)
				}
			)
			threshold = (
				*threshold_findings(rules, period, deliveries, figures),
				*threshold_unknown(rules, period, books_start, first_year.covered(prior)),
			)
			reconciliation = reconcile(statement, shares, figures, self._filed(covered))
			held = self._held() if self.meldeart == bridge.BERICHTIGUNG else None
			lines = bridge.line_rows(statement, confirmations, period, held)
		self.set("lines", lines)
		self.set("vouchers", bridge.voucher_rows(amounts, parties))
		self.set("reconciliation", bridge.reconciliation_rows(reconciliation))
		self.set("comparison", bridge.comparison_rows(compared))
		findings = [
			*statement.findings,
			*threshold,
			*reconciliation.findings,
			*comparison_hints(compared, before, figures),
			*((not_compared,) if not_compared else ()),
		]
		self.set("hints", bridge.hint_rows(findings))
		self._set_totals_and_status(statement)
		self.flags.calculating = True
		try:
			self.save()
		finally:
			self.flags.calculating = False

	@frappe.whitelist(methods=["POST"])
	@guards.on_stored("write")
	def confirm_vat_ids(self) -> int:
		"""USt-IdNrn. prüfen: ask about each USt-IdNr. the lines report, in a background job; returns how many
		numbers the job asks about. The query goes to the BZSt or VIES, so it needs the permission to submit, also
		while ERiC runs as a simulation."""
		guards.require_permission_to_send(self)
		self.lock_for_confirmation()
		if self.docstatus != 0:
			frappe.throw(_("Only the USt-IdNrn. of a draft Zusammenfassende Meldung are confirmed."))
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the statement before confirming its USt-IdNrn."))
		if cint(self.transmission_in_progress):
			frappe.throw(_("A transmission of {0} is running. Wait for its result.").format(self.name))
		self.refuse_if_sent()
		return self.start_confirmation(
			self.numbers_to_confirm(), CONFIRMATION_JOB, _("The statement reports no USt-IdNr. to confirm.")
		)

	def numbers_to_confirm(self) -> list[str]:
		"""The USt-IdNrn. the lines report, each once."""
		return bridge.numbers_to_confirm(self.lines)

	def details_for(self, vat_id: str) -> Details | None:
		"""Name and address of the customer of the first voucher of the lines of the number that names one."""
		return zm_sources.customer_details(bridge.customer_of(self.vouchers, vat_id))

	def take_in_confirmations(self) -> None:
		"""Every save builds the lines with the latest confirmation of their numbers, so the job saves the statement."""
		self.flags.confirming = True
		self.save()

	@frappe.whitelist(methods=["POST"])
	@guards.on_stored("write")
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
	@guards.on_stored("read")
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
					{field: row.get(field) for field in LINE_INPUT}
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
	@guards.on_stored("read")
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
	@guards.on_stored("submit")
	def mark_filed_outside(
		self,
		remarks: str | None = None,
		filed_via: str = OTHER_WAY,
		transferticket: str | None = None,
		filed_on: str | None = None,
	) -> str:
		"""In Mein ELSTER abgegeben, or Als außerhalb abgegeben vermerken: the statement went to the BZSt with
		the file for Mein ELSTER or another way. Submits it with how, when and by whom it was noted, and returns the
		name of the ELSTER Transmission that records it."""
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
		accepted = self.accepted_send()
		if accepted:
			frappe.throw(
				_(
					"ELSTER accepted {0} with Transferticket {1}, so it was not filed outside Steuerbote: submit it with Buchen."
				).format(self.name, accepted.transferticket)
			)
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
		return self.new_transmission(
			EXTERN,
			simulated=False,
			status=SUCCEEDED,
			remarks=note or None,
			filed_via=filed_via,
			transferticket=ticket or None,
			filed_on=filed_date,
		).name

	def datenart(self) -> eric_datenart.Datenart:
		"""The Datenart ZMDO, which has no year."""
		return eric_datenart.ZMDO

	def nutzdaten(self, hersteller_id: str) -> str:
		"""The Nutzdaten for ERiC: the element zm of the statement as saved, with the Unternehmer from the VAT Return
		Settings. ZMDO has no field for the Hersteller-ID, which only the TransferHeader names."""
		settings = settings_for(self.company)
		if not vatid.is_german(settings.ust_idnr):
			frappe.throw(
				_(
					"Enter the USt-IdNr. of {0} in the VAT Return Settings, DE and nine digits: the Zusammenfassende Meldung names the company by it."
				).format(self.company)
			)
		country = frappe.db.get_value(
			"Country", frappe.db.get_value("Company", self.company, "country"), "code"
		)
		period = self._chosen_period()
		with xml_errors(_("ELSTER Transmission")), zm_errors():
			statement = bridge.statement_of(self.vouchers, self.lines, self._figures())
			held = self._held() if self.meldeart == bridge.BERICHTIGUNG else None
			zm = bridge.zm(period, statement, held, self.anzeige, self.widerruf)
			return zm_xml.to_nutzdaten(bridge.unternehmer(settings, country), zm, getdate())

	def check_transmittable(self) -> None:
		"""A calculated draft whose USt-IdNrn. are not being confirmed."""
		if self.docstatus != 0:
			frappe.throw(
				_(
					"Only a draft Zusammenfassende Meldung can be transmitted. A filed one is corrected by a Berichtigung."
				)
			)
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the statement before transmitting it."))
		if cint(self.confirmation_in_progress):
			frappe.throw(_("The USt-IdNrn. of this statement are being confirmed. Wait for the result."))
		self._require_amounts_as_stored(self)

	def check_can_be_sent(self) -> None:
		"""Senden files the statement, once: it needs the statement fit for filing, the ledger of its months as
		Berechnen read it and no earlier filing of its Meldezeitraum."""
		self._check_ready_to_file()
		self._require_unchanged_ledger(self._coverage())
		self._refuse_sent_statement()
		self._refuse_second_filing()

	def _refuse_sent_statement(self) -> None:
		"""The BZSt has a statement whose Senden through Steuerbote ELSTER accepted, or may have it when the outcome
		is unknown: it is neither sent again nor made into the file for Mein ELSTER."""
		sent = self.filings()
		if sent and sent[0].status == UNKNOWN:
			frappe.throw(
				_(
					"Whether {0} reached ELSTER is unknown. Check in Mein ELSTER whether the statement arrived: if it did, note it with Filed in Mein ELSTER; if not, a System Manager deletes {0}, then the statement can be sent again."
				).format(sent[0].name)
			)
		if sent:
			frappe.throw(
				_(
					"This statement was transmitted already with Transferticket {0}. A change goes to the BZSt as a Berichtigung."
				).format(sent[0].transferticket)
			)

	def _lacks_mandatory_values(self) -> bool:
		return (
			not self.company
			or self.year is None
			or not self.period_kind
			or any(not row.art for row in self.lines)
		)

	def _refuse_a_period_before_the_start(self, period: ReportingPeriod) -> None:
		"""A Meldezeitraum that begins before the start of the books in Steuerbote was reported outside it, and the
		ledger holds only the opening balances of that time (steuerbote/setup/start.py): a statement computed from it
		would report nothing, and as a Berichtigung replace what the BZSt has."""
		books_start = prior_filings.books_start(self.company)
		if first_year.before_start(period.start, books_start):
			frappe.throw(
				_(
					"{0} begins before the start of the books in Steuerbote on {1}: its Zusammenfassende Meldung was filed outside Steuerbote, and the ledger holds only the opening balances of that time. A Berichtigung of it goes where the books of that time are kept."
				).format(period.label, formatdate(books_start))
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
		"""A Meldezeitraum counts as filed also when a statement of it was sent through Steuerbote, whether ELSTER
		accepted it or its outcome is unknown, so every other statement of it is a Berichtigung. A Berichtigung
		reports what changed against the filings when it was made, so none may follow."""
		self._refuse_second_statement(self._coverage())
		if self.meldeart != bridge.BERICHTIGUNG:
			others = frappe.get_all(
				DOCTYPE, filters={**self._period_filters(), "name": ["!=", self.name]}, pluck="name"
			)
			sent = filings(DOCTYPE, others)
			if sent:
				frappe.throw(
					_(
						"{0} of {1} was transmitted already as {2}. Clear its filing there first; a further statement of the Meldezeitraum is a Berichtigung of it."
					).format(self.period_label, self.company, sent[0].document)
				)
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

	def _keep_the_filing(self) -> None:
		"""Only the note of a filing sets the filing on a save, and a Senden ELSTER accepted sets it when it submits
		the statement (before_submit); every other save keeps it as stored."""
		before = self.get_doc_before_save()
		if before is not None and not self.flags.filed_outside:
			self.update({field: before.get(field) for field in FILING_FIELDS})

	def _keep_the_calculation(self, covered: Coverage) -> None:
		"""Rebuild the lines on every save, so that an override lifts its block at once and a confirmation counts
		as soon as it is stored.

		Frappe keeps no read-only field from a save through the API, so a save takes only the overrides and the
		lines of its own from the rows it sends: the status, the vouchers, the reconciliation and the comparison
		stay as Berechnen stored them, and so do the findings of the threshold, the reconciliation and the
		comparison among the hints; each USt-IdNr. counts with its latest VAT ID Confirmation. Company and
		Meldezeitraum stay as the statement was created (guards.Filing). A new statement is a draft (before_insert),
		so a calculated one was saved.
		"""
		before = self.get_doc_before_save()
		if before is None or self.flags.calculating:
			return
		self.update({"status": before.status, "ready": before.ready})
		for table in STORED_TABLES:
			self.set(table, _rows(before.get(table)))
		if self.status not in (CALCULATED, READY):
			self.set("lines", [{field: row.get(field) for field in LINE_INPUT} for row in self.lines])
			self.set("hints", _rows(before.hints))
			self.update({field: before.get(field) for field in TOTALS})
			return
		with zm_errors():
			amounts = bridge.voucher_amounts(self.vouchers)
			overrides = bridge.overrides_of(self.lines)
			statement, confirmations = self._build(amounts, overrides, covered, self._figures())
			held = self._held() if self.meldeart == bridge.BERICHTIGUNG else None
			rows = bridge.line_rows(statement, confirmations, covered.period, held)
		self.set("lines", rows)
		self.set("hints", bridge.merged_hints(statement, before.hints))
		self._set_totals_and_status(statement)

	def _build(
		self,
		amounts: list[VoucherAmount],
		overrides: dict[tuple[str, Art], Override],
		covered: Coverage,
		figures: SiteFigures,
	) -> tuple[Statement, dict[str, dict]]:
		"""The lines of the voucher amounts and the overrides, each USt-IdNr. with its latest confirmation for the
		months the statement reports, and that confirmation as the lines show it."""
		vat_ids = bridge.line_vat_ids(amounts, overrides)
		latest = vat_id_confirmation.latest(self.company, vat_ids)
		validity = bridge.validity_for(vat_ids, latest, bridge.covered_span(covered))
		statement = build(amounts, figures, validity, overrides, bridge.asked_on(latest))
		return statement, {vat_id: bridge.confirmation_fields(record) for vat_id, record in latest.items()}

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

	def _check_ready_to_file(self) -> None:
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the statement before filing it."))
		self._require_explanation()

	def _check_fit_for_filing(self) -> None:
		"""The statement is ready, and its lines are those of the file for Mein ELSTER of the ledger as it is."""
		self._check_ready_to_file()
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
		self._refuse_sent_statement()
		self._refuse_second_filing()
		self._require_explanation()
		self._require_unchanged_ledger(self._coverage())
		self._require_amounts_as_stored(self)

	def _require_amounts_as_stored(self, stored: Document) -> None:
		"""A filing carries the lines the statement holds, which every save builds from its vouchers and overrides,
		and what the lines report is what a later Berichtigung corrects: built again, they are the lines and the
		sums ``stored`` holds, or nothing is transmitted, made into a file or filed."""
		period = self._chosen_period()
		with zm_errors():
			statement = bridge.statement_of(self.vouchers, self.lines, self._figures())
			held = self._held() if self.meldeart == bridge.BERICHTIGUNG else None
			kept = bridge.amounts_kept(statement, period, held, stored)
		if not kept:
			frappe.throw(
				_(
					"The lines of {0} do not agree with its vouchers and overrides as stored. Reload the statement, and calculate it again if they still do not agree."
				).format(self.name)
			)

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
		covered = bridge.kept_coverage(period, self) or coverage_or_months(
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


def _rows(rows: Iterable[Document]) -> list[dict]:
	"""Rows of a table as they were stored, for a save to keep them."""
	return [row.as_dict(no_default_fields=True, no_child_table_fields=True) for row in rows]


@contextmanager
def zm_errors() -> Iterator[None]:
	"""Show a broken rule of the core as a message in the language of the user."""
	try:
		yield
	except ZmError as error:
		frappe.throw(_(error.template).format(*error.values), title=_("Recapitulative Statement"))


def run_confirmation(name: str) -> None:
	"""Background job of RecapitulativeStatement.confirm_vat_ids, see confirming.run: then the lines show the
	latest confirmation of their numbers."""
	confirming.run(DOCTYPE, name, UrllibFetch, _clock)


def _clock() -> datetime:
	return datetime.now(UTC)


def _thresholds(settings: Document) -> Thresholds:
	"""The thresholds of the Vorperiodenvergleich in the settings, as the report UStVA Kennzahlen reads them."""
	return Thresholds.of(
		settings.get("comparison_threshold_percent"), settings.get("comparison_threshold_amount")
	)
