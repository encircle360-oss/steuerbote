"""Annual Accounts: the Jahresabschluss of a GmbH or UG for one fiscal year, with its Feststellung and its Offenlegung
(§§ 242, 264, 266, 275, 325, 326 HGB, § 42a GmbHG).

The document lives on the base of the annual documents (steuerbote/steuerbote/annual_filing.py, docs/jahresmeldungen.md)
with the lifecycle ACCOUNTS: Entwurf, Berechnet, Festgestellt, Übermittelt, Eingestellt and Ersetzt. This controller
gives it the Jahresabschluss:

- Berechnen (compute) reads the books of the fiscal year and of the year before through the Balance Sheet Mapping
  (steuerbote/annual_accounts_sources.py), or the Vorjahr by hand, and the employees of the quarter ends
  (steuerbote/headcount.py); bridge.py decides the size class of § 267 HGB, builds the Bilanz and the GuV of the class
  with steuerbote/hgb/statement.py, each correction of a line taken in, and writes the lines, the Angaben of the
  catalogue of steuerbote/hgb/notes.py, the data of § 264 Abs. 1a HGB, the signatories and the findings.
- A save takes the corrections, the answers of the Angaben, the signatories, the Vorjahr by hand, the class and the
  Arbeitnehmer by hand with their reasons, the Ergebnisverwendung, the Offenlegung and the day of the Feststellung; a
  change of any leaves a calculated document Berechnet until Berechnen checks it again.
- Buchen is the Feststellung: whatever is acknowledged, it waits for Aktiva equal to Passiva, the Jahresergebnis of
  the Bilanz equal to that of the GuV, the data of § 264 Abs. 1a HGB, every Angabe answered, the explanation of an
  Eigenkapital of zero and the day of the Feststellung (check_filing), freezes the figures and records the day in the
  Annual Filing Settings (record_adoption). A Jahresabschluss that changes is cancelled and amended, and the amendment
  is festgestellt, signed and disclosed again (§ 325 Abs. 1b Satz 1 HGB).
- Übermittlung festhalten (record_transmission) moves it to Übermittelt with what the upload of steuerbote/hgb/upload.py
  records, after a dated signature, noted as filed_via upload for the deadline of the Offenlegung; Einstellung
  festhalten (record_publication) moves it to Eingestellt.
- The steps after Berechnen read the Jahresabschluss as stored, not as a form sends it.
- Vorschau der Offenlegung (make_disclosure_preview) prints what becomes visible into a private PDF, XBRL für das
  Unternehmensregister (make_xbrl, xbrl_export.py) writes the file of steuerbote/hgb/instance.py, and Ergebnisverwendung
  buchen (make_appropriation_entry) makes a draft Journal Entry of the resolution, which the company checks and
  submits: Steuerbote posts nothing.
"""

from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import Any

import frappe
from frappe import _
from frappe.core.doctype.file.utils import get_content_hash
from frappe.model.document import Document
from frappe.utils import cint, escape_html, flt, getdate

from steuerbote import annual_accounts_sources, balances, deadlines, headcount, holiday_list
from steuerbote.deadlines import Kind
from steuerbote.hgb import instance, schemes
from steuerbote.hgb.disclosure import adoption_problems
from steuerbote.hgb.notes import answer_problems, register_problems
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import ProfitPresentation
from steuerbote.jahresmeldung import acknowledgements
from steuerbote.jahresmeldung import findings as finding_rows
from steuerbote.jahresmeldung.findings import Finding, Severity
from steuerbote.jahresmeldung.lifecycle import ACCOUNTS, Event, Status
from steuerbote.jahresmeldung.overrides import to_amount
from steuerbote.ledger import account_names
from steuerbote.steuerbote.annual_filing import FINDINGS_TABLE, RECALCULATE, AnnualFiling, Calculation
from steuerbote.steuerbote.deadlines import annual_deadline, annual_rules
from steuerbote.steuerbote.doctype.annual_accounts import bridge, layout, xbrl_export
from steuerbote.steuerbote.doctype.annual_accounts.bridge import BridgeError, DisclosureMode, Problem
from steuerbote.steuerbote.doctype.annual_filing_settings.annual_filing_settings import record_adoption
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import SizeRecord, size_class_on

DOCTYPE = "Annual Accounts"
PRINT_FORMAT = "Jahresabschluss"
NOTES = "notes"
SIGNATORIES = "signatories"
PRIOR_ENTRIES = "prior_entries"
JOURNAL_ENTRY = "Journal Entry"
ELECTRONIC_BALANCE_SHEET = "Electronic Balance Sheet"
FINDING_DOCTYPE = "Annual Filing Finding"
SETTINGS = "Annual Filing Settings"
UG = "UG"
PREPARED = (SizeClass.KLEINST, SizeClass.KLEIN)
CHANNELS = ("XBRL-Upload", "Webformular", "Steuerberatung")
# Where the criteria of the previous Abschlussstichtag come from, as the field prior_criteria_source shows it.
PRIOR_FROM_BOOKS = "Hauptbuch des Vorjahres"
PRIOR_BY_HAND = "Vorjahr von Hand"
PRIOR_FROM_SETTINGS = "Größenmerkmale der Einstellungen Jahresmeldungen"
INPUT_FIELDS = (
	"size_class_override",
	"size_class_override_reason",
	"employees_override",
	"employees_override_reason",
	"presentation",
	"prior_net_income",
	"prior_source",
	"in_liquidation",
	"adopted_on",
	"appropriation_reserve",
	"appropriation_dividend",
	"disclosure_mode",
)
"""What Berechnen reads of the document besides its lines and its tables."""
INPUT_TABLES = MappingProxyType(
	{
		"notes": ("code", "answer", "text", "amount"),
		"signatories": ("signatory_name", "function", "place", "signed_on"),
		"prior_entries": ("concept", "amount", "shareholder", "remaining_term"),
	}
)
"""The tables Berechnen reads, with the columns the company enters."""
RECORDED_FIELDS = (
	"channel",
	"transmitted_on",
	"transmitted_by",
	"order_number",
	"confirmation_file",
	"kleinst_notice",
	"published_on",
	"receipt_file",
	"fees",
	"preview_file",
	"xbrl_file",
	"appropriation_entry",
)
"""What Übermittlung festhalten, Einstellung festhalten, the files and the Ergebnisverwendung set, never a save."""
ADOPTION_FIELDS = ("adopted_on", "resolution_file")
"""What a new Jahresabschluss starts without: an amendment is festgestellt again (§ 325 Abs. 1b Satz 1 HGB)."""


class AnnualAccounts(AnnualFiling, Document):
	LIFECYCLE = ACCOUNTS
	LINES = "lines"
	LINE_COLUMNS = bridge.LINE_COLUMNS
	CALCULATED_FIELDS = (
		"bilanzsumme",
		"umsatzerloese",
		"employees_counted",
		"headcount_detail",
		"employees",
		"prior_bilanzsumme",
		"prior_umsatzerloese",
		"prior_employees",
		"prior_criteria_source",
		"prior_size_class",
		"size_class_computed",
		"size_basis",
		"size_class",
		"net_income",
		"carried_forward",
		"equity",
		"has_prior",
		"prior_from_date",
		"prior_to_date",
		"statement_data",
		"firma",
		"sitz",
		"register_court",
		"register_number",
		"legal_form",
		"ug_reserve_minimum",
	)

	# The hooks of the base.

	def compute(self) -> Calculation:
		"""Berechnen: the size class, the Bilanz and the GuV of the class, the Angaben, the signatories and the
		findings."""
		self._refuse_an_unknown_year()
		year = cint(self.year)
		from_date, to_date = getdate(self.from_date), getdate(self.to_date)
		settings = annual_accounts_sources.settings(self.company)
		sources = annual_accounts_sources.statement_sources(self.company, self.fiscal_year)
		not_counted = settings.employment_types_not_counted()
		counted = headcount.count(self.company, to_date, not_counted)
		history = settings.get_size_history()
		directors = settings.get_directors()
		founded = annual_accounts_sources.founded_in(self.company, from_date, to_date)
		register = bridge.register_values(
			annual_accounts_sources.company_name(self.company), settings.as_dict()
		)
		adopted_on = bridge.day_of(self.adopted_on)
		with bridge_errors():
			prior, prior_net_income, prior_dates, prior_origin = self._prior(sources, year, from_date)
			presentation = self._presentation()
			options = {
				"parents": sources.parents,
				"prior": prior,
				"prior_net_income": prior_net_income,
				"presentation": presentation,
				"corrections": bridge.corrections_of(self._rows(self.LINES)),
			}
			# The criteria and the Gewinnvortrag are read from the form of klein, which shows both.
			preliminary = bridge.statements(year, SizeClass.KLEIN, sources.balances, **options)
			values = bridge.statement_values(preliminary.filed)
			employees, employee_findings = bridge.employees_applied(
				counted.average, *self._employees_override()
			)
			current = bridge.criteria(to_date, values["bilanzsumme"], values["umsatzerloese"], employees)
			prior_end = prior_dates[1] if prior_dates else from_date - timedelta(days=1)
			previous_record = record_of(history, prior_end)
			books_previous = None
			prior_values = bridge.prior_values(preliminary.filed)
			if prior_values is not None:
				books_previous = bridge.criteria(
					prior_end,
					prior_values["bilanzsumme"],
					prior_values["umsatzerloese"],
					headcount.count(self.company, prior_end, not_counted).average,
				)
			previous = bridge.previous_criteria(previous_record, books_previous)
			if previous is None:
				criteria_source = ""
			else:
				criteria_source = prior_origin if previous is books_previous else PRIOR_FROM_SETTINGS
			decision = bridge.decide(
				current,
				previous,
				bridge.size_class_of(previous_record.size_class) if previous_record else None,
				founded_in_year=founded,
				excluded_from_kleinst=bool(cint(settings.holding_267a_3)),
			)
			applied, class_findings = bridge.applied_class(
				decision,
				bridge.size_class_of(self.size_class_override),
				self.size_class_override_reason or "",
			)
			found = (
				preliminary
				if applied in (None, SizeClass.KLEIN)
				else bridge.statements(year, applied, sources.balances, **options)
			)
			requested = (
				(self.disclosure_mode or settings.kleinst_mode) if applied is SizeClass.KLEINST else ""
			)
			mode = bridge.mode_of(requested, applied)
			# The statement of the class takes the corrections of its own lines, which the form of klein may not have.
			equity = found.filed.balance_sheet.equity
			net_income = found.filed.income_statement.net_income
			appropriation = bridge.Appropriation(
				net_income,
				values["carried_forward"],
				to_amount(self.appropriation_reserve),
				to_amount(self.appropriation_dividend),
				settings.legal_form == UG,
			)
			entries = bridge.catalogue_of(applied, equity_zero=equity == 0)
			notes = bridge.note_rows(entries, self._rows(NOTES))
			signatories = self._rows(SIGNATORIES) or bridge.signatory_rows(
				directors, adopted_on or to_date, register["sitz"]
			)
			found_findings = [
				*sources.findings,
				*bridge.annual_findings(found.filed.findings),
				*bridge.refused_findings(found.refused),
				*class_findings,
				*employee_findings,
				*bridge.employment_type_finding(not_counted, counted.typed),
				*bridge.size_findings(decision, applied, record_of(history, to_date)),
				*bridge.prior_finding(prior is not None, founded),
				*bridge.annual_findings(
					register_problems(
						bridge.register_of(register, in_liquidation=bool(cint(self.in_liquidation)))
					)
				),
				*bridge.annual_findings(answer_problems(entries, bridge.answers_of(notes, employees))),
				*bridge.annual_findings(
					adoption_problems(
						to_date,
						adopted_on,
						bridge.signing_directors(directors),
						bridge.signatures_of(signatories),
					)
				),
				*bridge.appropriation_findings(appropriation),
				*bridge.deposit_finding(applied, mode),
			]
			statement_data = bridge.statement_data(
				found, prior, sources.parents, prior_net_income=prior_net_income, presentation=presentation
			)
		calculated: dict[str, Any] = {
			"bilanzsumme": values["bilanzsumme"],
			"umsatzerloese": values["umsatzerloese"],
			"employees_counted": counted.average,
			"headcount_detail": bridge.headcount_text(counted.counts),
			"employees": employees,
			"prior_bilanzsumme": previous.bilanzsumme if previous else Decimal(0),
			"prior_umsatzerloese": previous.umsatzerloese if previous else Decimal(0),
			"prior_employees": previous.arbeitnehmer if previous else Decimal(0),
			"prior_criteria_source": criteria_source,
			"prior_size_class": previous_record.size_class if previous_record else "",
			"size_class_computed": bridge.stored_class(decision.applied),
			"size_basis": decision.basis.value if decision.basis else "",
			"size_class": bridge.stored_class(applied),
			"net_income": net_income,
			"carried_forward": values["carried_forward"],
			"equity": equity,
			"has_prior": int(prior is not None),
			"prior_from_date": prior_dates[0] if prior is not None else None,
			"prior_to_date": prior_dates[1] if prior is not None else None,
			"statement_data": statement_data,
			**register,
			"legal_form": settings.legal_form,
			"ug_reserve_minimum": appropriation.minimum_reserve,
			"disclosure_mode": bridge.stored_mode(mode),
		}
		return Calculation(
			lines=bridge.line_rows(found, sources.parents),
			tables={NOTES: notes, SIGNATORIES: signatories},
			values=calculated,
			findings=found_findings,
		)

	def compute_deadline(self) -> date | None:
		"""The last day of the Feststellung, as Offene Fristen lists it: eight months after the fiscal year, eleven for a
		small company (§ 42a Abs. 2 Satz 1 GmbHG)."""
		return annual_deadline(self.company, Kind.FESTSTELLUNG, cint(self.year))

	def set_period(self) -> None:
		"""Besides the fiscal year and the Feststellung, the last day of the Offenlegung (§ 325 Abs. 1a Satz 1 HGB). Where
		the settings name no size class for the Abschlussstichtag, the class Berechnen applied gives the deadline of the
		Feststellung, eleven months for a small company (§ 42a Abs. 2 Satz 1 GmbHG)."""
		super().set_period()
		self.disclosure_deadline = annual_deadline(self.company, Kind.OFFENLEGUNG, cint(self.year))
		rules = annual_rules(self.company)
		closing = getdate(self.to_date)
		if rules is not None and self.size_class and size_class_on(rules.size_history, closing) is None:
			applied = SizeRecord(closing, self.size_class, _(DOCTYPE))
			rules = replace(rules, size_history=(*rules.size_history, applied))
			self.deadline = deadlines.annual_due(
				rules, Kind.FESTSTELLUNG, cint(self.year), holiday_list.holidays(self.company)
			)

	def set_amounts(self) -> None:
		"""The Vortrag auf neue Rechnung of the Ergebnisverwendung."""
		self.appropriation_carried = self._appropriation().carried

	def amounts_kept(self, stored: Document) -> bool:
		return to_amount(stored.appropriation_carried) == self._appropriation().carried

	def check_filing(self) -> None:
		"""What holds the Feststellung back, whatever is acknowledged (bridge.filing_problems)."""
		problems = bridge.filing_problems(
			self.name,
			self._rows(self.LINES),
			self._rows(NOTES),
			bridge.register_of(self.as_dict(), in_liquidation=bool(cint(self.in_liquidation))),
			size_class=bridge.size_class_of(self.size_class),
			adopted_on=bridge.day_of(self.adopted_on),
			to_date=getdate(self.to_date),
			today=getdate(),
			codes={row.code for row in self.get(FINDINGS_TABLE) or ()},
			recalculate=RECALCULATE,
		)
		refuse(problems, _("Feststellung"))

	# Frappe.

	def before_insert(self) -> None:
		"""A new Jahresabschluss records nothing of an Übermittlung, a file or an Ergebnisverwendung and starts without
		the day of the Feststellung. An amendment keeps the Angaben and the signatories of the one it amends, the
		signatures without their dates; any other copy starts without both."""
		super().before_insert()
		self.update({**dict.fromkeys(RECORDED_FIELDS), **dict.fromkeys(ADOPTION_FIELDS), "kleinst_notice": 0})
		if self.amended_from:
			for row in self.get(SIGNATORIES) or ():
				row.signed_on = None
		else:
			self.set(NOTES, [])
			self.set(SIGNATORIES, [])

	def validate(self) -> None:
		before = self.get_doc_before_save()
		self._refuse_an_unknown_year()
		if self.company and self.year:
			self._keep_the_entered_tables(before)
			self._keep_the_records(before)
			self._set_the_presentation()
		super().validate()
		if not (self.company and self.year):
			return
		with bridge_errors():
			self._check_the_prior_entries()
			self._check_the_overrides()
			self._check_the_disclosure()
		refuse(
			bridge.appropriation_problems(self._appropriation(), calculated=bool(self.statement_data)),
			_("Ergebnisverwendung"),
		)
		refuse(bridge.correction_problems(self._rows(self.LINES)), _(DOCTYPE))
		self._require_berechnen_after_a_change(before)

	def on_submit(self) -> None:
		"""The Feststellung: its day goes into the Annual Filing Settings."""
		super().on_submit()
		record_adoption(self.company, cint(self.year), getdate(self.adopted_on))

	def on_cancel(self) -> None:
		"""A cancelled Jahresabschluss is no longer festgestellt; its amendment records its own day. An E-Bilanz filed
		with it keeps naming it as the Jahresabschluss Berechnen compared it with and holds no cancellation back: the
		Berichtigung of the E-Bilanz is compared with the amendment."""
		self.ignore_linked_doctypes = (ELECTRONIC_BALANCE_SHEET,)
		record_adoption(self.company, cint(self.year), None)

	# The steps after Berechnen.

	@frappe.whitelist(methods=["POST"])
	def make_disclosure_preview(self) -> str:
		"""Vorschau der Offenlegung: what becomes visible, printed with the PDF engine of the Print Settings into a
		private PDF attached to the document. Returns its address."""
		self.check_permission("write")
		self.reload()
		self._require_calculated()
		self.flags.offenlegung = True
		try:
			content = frappe.get_print(DOCTYPE, self.name, PRINT_FORMAT, doc=self, as_pdf=True)
		finally:
			self.flags.offenlegung = False
		url = attach(self, f"Vorschau-Offenlegung-{self.name}.pdf", content)
		self.db_set("preview_file", url, update_modified=False)
		return url

	@frappe.whitelist(methods=["POST"])
	def make_xbrl(self) -> dict[str, Any]:
		"""XBRL für das Unternehmensregister: the file of the Offenlegung, attached privately, or the findings that hold
		it back, which take the place of those of the file before in the table Befunde."""
		self.check_permission("write")
		self.reload()
		self.require_fit_for_export()
		size_class = bridge.size_class_of(self.size_class)
		if size_class not in PREPARED:
			frappe.throw(
				_(
					"Steuerbote writes the XBRL of a Kleinstkapitalgesellschaft and of a small company only; the Offenlegung of a larger one is left to the Steuerberatung or the Abschlussprüfer."
				)
			)
		with bridge_errors():
			mode = bridge.mode_of(self.disclosure_mode, size_class)
		try:
			content = xbrl_export.offenlegung(self, size_class, mode)
		except instance.HeldBackError as error:
			held = bridge.annual_findings(error.findings)
			self._keep_the_findings_of_the_file(held)
			return {"file_url": "", "held_back": [finding.text for finding in held]}
		except instance.InstanceError as error:
			frappe.throw(
				_("The XBRL of {0} cannot be written: {1}").format(self.name, escape_html(str(error)))
			)
		self._keep_the_findings_of_the_file(())
		url = attach(self, xbrl_export.file_name(self), content)
		self.db_set("xbrl_file", url, update_modified=False)
		return {"file_url": url, "held_back": []}

	@frappe.whitelist(methods=["POST"])
	def record_transmission(
		self,
		transmitted_on: str,
		transmitted_by: str,
		order_number: str,
		channel: str | None = None,
		confirmation_file: str | None = None,
		fees: float | str | None = None,
		kleinst_notice: int | str | None = 0,
	) -> str:
		"""Übermittlung festhalten: the festgestellter Jahresabschluss went to the Unternehmensregister
		(steuerbote/hgb/upload.py, RECORDS). Moves it to Übermittelt, noted as filed_via upload on the day of the
		upload, which keeps the deadline of the Offenlegung (§ 325 Abs. 4 Satz 2 HGB). Returns the new status."""
		self.check_permission("submit")
		self.reload()
		if self.docstatus != 1 or self.status != Status.ADOPTED:
			frappe.throw(_("{0} is not festgestellt, so it is not transmitted.").format(self.name))
		channel = channel or CHANNELS[0]
		if channel not in CHANNELS:
			frappe.throw(_("Steuerbote knows no channel {0}.").format(escape_html(str(channel))))
		transmitted_by, order_number = (transmitted_by or "").strip(), (order_number or "").strip()
		if not transmitted_by:
			frappe.throw(
				_(
					"Enter who transmitted the Jahresabschluss: the person who identified herself and uploaded it (§ 3a Abs. 1 URV)."
				)
			)
		day = getdate(transmitted_on)
		with bridge_errors():
			mode = bridge.mode_of(self.disclosure_mode, bridge.size_class_of(self.size_class))
		notice = bool(cint(kleinst_notice))
		refuse(
			bridge.transmission_record_problems(
				adopted_on=bridge.day_of(self.adopted_on),
				transmitted_on=day,
				today=getdate(),
				signatures=bridge.signatures_of(self._rows(SIGNATORIES)),
				mode=mode,
				notice=notice,
				order_number=order_number,
			),
			_("Übermittlung"),
		)
		self._require_own_file(confirmation_file)
		status = self.move_on(Event.TRANSMIT, filed_via="upload", filed_on=day, note=order_number)
		self.db_set(
			{
				"channel": channel,
				"transmitted_on": day,
				"transmitted_by": transmitted_by,
				"order_number": order_number,
				"confirmation_file": confirmation_file or None,
				"fees": flt(fees),
				"kleinst_notice": int(notice and bridge.stored_mode(mode) == DisclosureMode.HINTERLEGUNG),
			}
		)
		return status

	@frappe.whitelist(methods=["POST"])
	def record_publication(
		self, published_on: str, receipt_file: str | None = None, fees: float | str | None = None
	) -> str:
		"""Einstellung festhalten: the Unternehmensregister has eingestellt the Jahresabschluss, with the PDF-Beleg of the
		order. Moves it to Eingestellt and returns the new status."""
		self.check_permission("submit")
		self.reload()
		if self.docstatus != 1 or self.status != Status.TRANSMITTED:
			frappe.throw(_("{0} is not transmitted, so it is not eingestellt.").format(self.name))
		day = getdate(published_on)
		refuse(
			bridge.publication_record_problems(getdate(self.transmitted_on), day, getdate()),
			_("Einstellung"),
		)
		self._require_own_file(receipt_file)
		status = self.move_on(Event.PUBLISH)
		values: dict[str, Any] = {"published_on": day, "receipt_file": receipt_file or None}
		if fees not in (None, ""):
			values["fees"] = flt(fees)
		self.db_set(values)
		return status

	@frappe.whitelist(methods=["POST"])
	def make_appropriation_entry(self) -> str:
		"""Ergebnisverwendung buchen: a draft Journal Entry of the resolution on the day of the Feststellung, on the
		accounts of the chart (bridge.APPROPRIATION_ACCOUNTS), which the company checks and submits. Returns its name."""
		self.check_permission("write")
		frappe.has_permission(JOURNAL_ENTRY, "create", throw=True)
		self.reload()
		if self.docstatus != 1:
			frappe.throw(
				_("The Ergebnisverwendung follows the Feststellung: submit {0} first.").format(self.name)
			)
		if self.appropriation_entry and frappe.db.exists(
			JOURNAL_ENTRY, {"name": self.appropriation_entry, "docstatus": 0}
		):
			frappe.throw(
				_(
					"The draft Journal Entry {0} holds the Ergebnisverwendung proposed before. Check and submit it, or delete it to propose it again."
				).format(self.appropriation_entry)
			)
		chart = frappe.db.get_value(annual_accounts_sources.MAPPING, self.company, "chart")
		accounts = bridge.APPROPRIATION_ACCOUNTS.get(chart)
		if accounts is None:
			frappe.throw(_(bridge.NO_APPROPRIATION_ACCOUNTS))
		closing = balances.closing_account(self.company)
		if not closing or not closing[1]:
			frappe.throw(
				_(
					"Name the closing account of {0} with its account number in the Annual Filing Settings: it holds the result the Ergebnisverwendung distributes."
				).format(escape_html(self.company))
			)
		with bridge_errors():
			rows = bridge.appropriation_rows(
				self._appropriation(),
				accounts,
				closing[1],
				reserve_in_books=self.presentation == ProfitPresentation.AFTER_PARTIAL_APPROPRIATION.value,
			)
		name = appropriation_entry(self.company, getdate(self.adopted_on), rows, self.name)
		self.db_set("appropriation_entry", name, update_modified=False)
		return name

	# What the print format reads.

	def annual_accounts_print(self) -> dict[str, Any]:
		"""The Bilanz, the GuV, the Angaben, the signatures, what becomes visible and the upload, for the print format
		„Jahresabschluss“ and its Vorschau der Offenlegung (layout.py)."""
		rows, notes = self._rows(self.LINES), self._rows(NOTES)
		size_class = bridge.size_class_of(self.size_class)
		employees = Decimal(str(flt(self.employees)))
		try:
			mode = bridge.mode_of(self.disclosure_mode, size_class)
		except BridgeError:
			mode = bridge.mode_of("", size_class)
		return {
			"account_form": layout.account_form(rows),
			"guv": layout.income_statement(rows),
			"notes": layout.notes(notes, employees, published_only=False),
			"published_notes": layout.notes(notes, employees, published_only=True),
			"register": layout.register_lines(self.as_dict(), in_liquidation=bool(cint(self.in_liquidation))),
			"signatures": layout.signature_lines(self._rows(SIGNATORIES)),
			"visibility": layout.visibility(size_class, mode),
			"upload": layout.upload_guide(
				size_class, mode, cint(self.year), first_upload=self._first_upload()
			),
			"kleinst": size_class is SizeClass.KLEINST,
			"preview": bool(self.flags.offenlegung),
		}

	# The rules of a save.

	def _keep_the_entered_tables(self, before: Document | None) -> None:
		"""A save keeps the table Angaben as Berechnen wrote it and takes the answers alone; another key discards the
		Angaben and the signatories, which Berechnen starts again for it."""
		if before is None or self.flags.calculating:
			return
		if self._key_of(before) != self._key_of(self):
			self.set(NOTES, [])
			self.set(SIGNATORIES, [])
			return
		self.set(NOTES, bridge.notes_kept(self._rows(NOTES, before), self._rows(NOTES)))

	def _keep_the_records(self, before: Document | None) -> None:
		"""Only the steps of the Offenlegung set what they record; a save keeps it as stored."""
		if before is not None:
			self.update({fieldname: before.get(fieldname) for fieldname in RECORDED_FIELDS})

	def _set_the_presentation(self) -> None:
		"""Left empty, the presentation follows the legal form: an UG forms its gesetzliche Rücklage in the Bilanz of
		the year (§ 5a Abs. 3 Satz 1 GmbHG), so it presents its result after part of the appropriation."""
		if self.presentation:
			return
		ug = frappe.db.get_value(SETTINGS, self.company, "legal_form") == UG
		chosen = (
			ProfitPresentation.AFTER_PARTIAL_APPROPRIATION if ug else ProfitPresentation.BEFORE_APPROPRIATION
		)
		self.presentation = chosen.value

	def _check_the_prior_entries(self) -> None:
		"""The Vorjahr by hand names positions of the schemes of the year and where its figures come from."""
		rows = self.get(PRIOR_ENTRIES) or []
		if not rows:
			return
		if not (self.prior_source or "").strip():
			raise BridgeError(bridge.PRIOR_WITHOUT_SOURCE)
		for row in rows:
			row.concept = (row.concept or "").strip()
		for row, label in zip(
			rows, bridge.prior_labels(self._rows(PRIOR_ENTRIES), cint(self.year)), strict=True
		):
			row.label = label

	def _check_the_overrides(self) -> None:
		"""A class or Arbeitnehmer by hand count once they have their reason; without one a save refuses them, since
		whoever entered them expects them to count."""
		if self.size_class_override and not (self.size_class_override_reason or "").strip():
			raise BridgeError(bridge.OVERRIDE_WITHOUT_REASON, "Größenklasse")
		if flt(self.employees_override) and not (self.employees_override_reason or "").strip():
			raise BridgeError(bridge.OVERRIDE_WITHOUT_REASON, "Arbeitnehmer")

	def _check_the_disclosure(self) -> None:
		"""Only a Kleinstkapitalgesellschaft deposits (§ 326 Abs. 2 HGB); before Berechnen knows the class, the choice
		waits for it."""
		size_class = bridge.size_class_of(self.size_class)
		if size_class is not None:
			bridge.mode_of(self.disclosure_mode, size_class)

	def _require_berechnen_after_a_change(self, before: Document | None) -> None:
		"""A calculated Jahresabschluss whose entries changed is Berechnet again, with a finding that asks for
		Berechnen."""
		if before is None or self.flags.calculating or self.status not in self.LIFECYCLE.calculated:
			return
		if inputs(before) == inputs(self):
			return
		self.status = self.LIFECYCLE.move(self.status, Event.CHANGE)
		self.ready = 0
		stored = finding_rows.of_rows(self._rows(FINDINGS_TABLE))
		if any(finding.code == RECALCULATE for finding in stored):
			return
		recalculate = Finding(
			RECALCULATE,
			Severity.ERROR,
			_(
				"An entry that Berechnen reads changed since Berechnen: an Angabe, a signatory, the Vorjahr by hand, the size class or the Arbeitnehmer by hand, the Ergebnisverwendung, the Offenlegung or the day of the Feststellung. Calculate again, so that Berechnen checks the Jahresabschluss with it."
			),
		)
		self.add_finding(recalculate)

	def _keep_the_findings_of_the_file(self, held: Sequence[Finding]) -> None:
		"""The findings that hold the file back take the place of those of the file before; the others stay. The table
		is written directly, since a festgestellter Jahresabschluss keeps its fields."""
		stored = self._rows(FINDINGS_TABLE)
		kept = [finding for finding in finding_rows.of_rows(stored) if not bridge.xbrl_code(finding.code)]
		frappe.db.delete(
			FINDING_DOCTYPE, {"parent": self.name, "parenttype": self.doctype, "parentfield": FINDINGS_TABLE}
		)
		self.set(FINDINGS_TABLE, [])
		for row in acknowledgements.carried(finding_rows.rows((*kept, *held)), stored):
			child = self.append(FINDINGS_TABLE, row)
			child.docstatus = self.docstatus
			child.db_insert()

	# Helpers.

	def _refuse_an_unknown_year(self) -> None:
		"""A Jahresabschluss of a year without the size thresholds and the schemes of the HGB is no draft Berechnen
		could calculate, as the Erklärungen refuse a year without their forms."""
		if self.year and cint(self.year) not in schemes.years():
			known = ", ".join(str(year) for year in sorted(schemes.years()))
			frappe.throw(
				_(
					"Steuerbote has no Jahresabschluss for {0} yet: it knows the size classes and schemes of {1}."
				).format(cint(self.year), known)
			)

	def _prior(
		self, sources: annual_accounts_sources.Sources, year: int, from_date: date
	) -> tuple[tuple | None, Decimal | None, tuple[date, date] | None, str]:
		"""The previous year with its Jahresergebnis where it has no GuV, its days and where it comes from: the Vorjahr
		by hand where the document has one, else the books."""
		rows = self._rows(PRIOR_ENTRIES)
		if rows:
			return (
				bridge.prior_balances(rows, year),
				to_amount(self.prior_net_income),
				bridge.prior_period(from_date, sources.prior_dates),
				PRIOR_BY_HAND,
			)
		return sources.prior, None, sources.prior_dates, PRIOR_FROM_BOOKS

	def _presentation(self) -> ProfitPresentation:
		return bridge.PRESENTATIONS.get(self.presentation, ProfitPresentation.BEFORE_APPROPRIATION)

	def _employees_override(self) -> tuple[Decimal | None, str]:
		"""The Arbeitnehmer by hand count once they have their reason, zero as well."""
		reason = (self.employees_override_reason or "").strip()
		return (Decimal(str(flt(self.employees_override))) if reason else None), reason

	def _appropriation(self) -> bridge.Appropriation:
		return bridge.Appropriation(
			to_amount(self.net_income),
			to_amount(self.carried_forward),
			to_amount(self.appropriation_reserve),
			to_amount(self.appropriation_dividend),
			self.legal_form == UG,
		)

	def _require_calculated(self) -> None:
		if self.docstatus == 2 or self.status not in (*self.LIFECYCLE.calculated, *self.LIFECYCLE.filings):
			frappe.throw(_("Calculate {0} first.").format(self.name))

	def _require_own_file(self, file_url: str | None) -> None:
		"""A file the Übermittlung or the Einstellung records is one attached privately to this Jahresabschluss."""
		if file_url and not frappe.db.exists(
			"File",
			{
				"file_url": file_url,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"is_private": 1,
			},
		):
			frappe.throw(
				_("{0} is no file attached privately to {1}.").format(escape_html(file_url), self.name)
			)

	def _first_upload(self) -> bool:
		"""Whether no Jahresabschluss of the company went to the Unternehmensregister before this one."""
		return not frappe.db.exists(
			DOCTYPE,
			{"company": self.company, "name": ["!=", self.name or ""], "transmitted_on": ["is", "set"]},
		)

	def amends_transmitted(self) -> bool:
		"""Whether the document amends a Jahresabschluss that went to the Unternehmensregister, so that its file states
		a changed one (§ 325 Abs. 1b Satz 1 HGB)."""
		return bool(self.amended_from) and bool(
			frappe.db.get_value(DOCTYPE, self.amended_from, "transmitted_on")
		)

	def _rows(self, table: str, doc: Document | None = None) -> list[dict[str, Any]]:
		return [row.as_dict() for row in (doc or self).get(table) or ()]


def record_of(history: Iterable[Any], closing_date: date) -> Any:
	"""The row of the size history of the Annual Filing Settings for an Abschlussstichtag, None without one."""
	return next((record for record in history if record.fiscal_year_end == closing_date), None)


def refuse(problems: Iterable[Problem], title: str) -> None:
	"""Refuse the step with every problem of the bridge, in the language of the user."""
	messages = [message(problem) for problem in problems]
	if messages:
		frappe.throw("<br>".join(messages), title=title)


def message(problem: Problem) -> str:
	return _(problem.template).format(*(escape_html(str(value)) for value in problem.values))


@contextmanager
def bridge_errors() -> Iterator[None]:
	"""Show what the bridge refuses as a message in the language of the user."""
	try:
		yield
	except BridgeError as error:
		frappe.throw(message(Problem(error.template, error.values)), title=_(DOCTYPE))


def inputs(doc: Document) -> tuple:
	"""What Berechnen reads of the document besides its lines, comparable between two states of it."""
	values = tuple(_input(doc, fieldname) for fieldname in INPUT_FIELDS)
	tables = tuple(
		tuple(tuple(_input(row, column) for column in columns) for row in doc.get(table) or ())
		for table, columns in INPUT_TABLES.items()
	)
	return values, tables


def _input(doc: Document, fieldname: str) -> str:
	value = doc.get(fieldname)
	fieldtype = doc.meta.get_field(fieldname).fieldtype
	if fieldtype in ("Check", "Int"):
		return str(cint(value))
	if fieldtype in ("Currency", "Float"):
		return format(to_amount(value), "f")
	if fieldtype == "Date":
		return getdate(value).isoformat() if value else ""
	return " ".join(str(value or "").split())


def attach(doc: Document, file_name: str, content: bytes) -> str:
	"""Attach the file privately to the document; a file of the same content attached before is kept instead."""
	attached = frappe.db.get_value(
		"File",
		{
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
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
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"is_private": 1,
			"content": content,
		}
	)
	file.insert()
	return file.file_url


def appropriation_entry(
	company: str, posting_date: date, rows: Iterable[bridge.EntryRow], document: str
) -> str:
	"""The draft Journal Entry of the Ergebnisverwendung, a row of it for each row of the bridge. Returns its name."""
	rows = list(rows)
	numbers = sorted({row.account for row in rows})
	names = account_names(company, numbers)
	missing = [number for number in numbers if number not in names]
	if missing:
		frappe.throw(
			_(
				"{0} lacks the accounts {1} of the Ergebnisverwendung. Create them before posting the Ergebnisverwendung."
			).format(escape_html(company), ", ".join(missing))
		)
	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	entry = frappe.get_doc(
		{
			"doctype": JOURNAL_ENTRY,
			"voucher_type": JOURNAL_ENTRY,
			"company": company,
			"posting_date": posting_date,
			"user_remark": _("Ergebnisverwendung of {0}").format(document),
			"accounts": [
				{
					"account": names[row.account],
					"debit_in_account_currency": row.debit,
					"credit_in_account_currency": row.credit,
					"cost_center": cost_center,
					"user_remark": row.remark,
				}
				for row in rows
			],
		}
	)
	entry.insert()
	return entry.name
