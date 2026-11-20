"""VAT Return Extension: form USt 1 H of one company for one year, the Antrag auf Dauerfristverlängerung and
the Anmeldung der Sondervorauszahlung (§§ 46 to 48 UStDV).

The VAT Return Settings prescribe the rhythm of the first month the form covers, and the rhythm sets the form:
a monthly filer registers the Sondervorauszahlung, a quarterly one applies for the Dauerfristverlängerung alone
(steuerbote.dauerfrist.form.Context.for_rhythm). Every save sets the deadline through steuerbote.dauerfrist,
with the holidays of the company's Holiday List. "Berechnen" (calculate) reads the VAT Returns filed for the
previous year and the date of establishment of the company through steuerbote.dauerfrist_sources; the core
computes the base and Kz 38 from them, and bridge.py moves the values. A base by hand with a reason replaces
the base from the Voranmeldungen, and Kz 38 follows it on every save.

"Prüfen", "Testsenden" and "Senden" (transmit) run in a background job, as for every document that goes to
ELSTER through ERiC (elster_transmission/transmission.py): the job writes form USt 1 H with the Hersteller-ID in
Kz 09 (nutzdaten, steuerbote.elster.ust1h_xml) and hands it to steuerbote.eric, through the worker of an installed
runtime or the simulation; every run is recorded as an ELSTER Transmission. Only a Senden that ELSTER accepted
submits the form, which files it through ERiC with its Transferticket. Mein ELSTER takes no file for form USt 1 H,
so without ERiC the form is entered there by hand: "In Mein ELSTER eingetragen" and "Als außerhalb abgegeben
vermerken" (mark_filed_outside) submit it with a note of the filing, recorded as an ELSTER Transmission as well.
The submission writes the Sondervorauszahlung into the row of its year in the VAT Return Settings, from which the
last Voranmeldung of the year deducts it in Kz 39. Submitting alone ("Buchen") files nothing and is refused,
except for a form that ELSTER accepted while its submission failed. A company files one form a year: once a form
of the year is filed or sent through Steuerbote, cancelled or not, a further one is a corrected Anmeldung (Kz 10).
A filed Anmeldung der Sondervorauszahlung is corrected by cancelling it and amending it into a corrected
Anmeldung, which the Antrag alone does not allow.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, escape_html, formatdate, getdate

from steuerbote import dauerfrist, dauerfrist_sources, holiday_list
from steuerbote.dauerfrist import Context, FormError, layout_for
from steuerbote.elster import ust1h_xml, ustva_xml
from steuerbote.steuerbote.doctype.elster_transmission.elster_transmission import (
	EXTERN,
	FILED_VIA,
	OTHER_WAY,
	SUCCEEDED,
	UNKNOWN,
)
from steuerbote.steuerbote.doctype.elster_transmission.transmission import Transmittable, filings
from steuerbote.steuerbote.doctype.vat_return import bridge as vat_return_bridge
from steuerbote.steuerbote.doctype.vat_return.vat_return import TRANSFERTICKET, settings_for
from steuerbote.steuerbote.doctype.vat_return_extension import bridge
from steuerbote.steuerbote.doctype.vat_return_settings import rules
from steuerbote.steuerbote.doctype.vat_return_settings.vat_return_settings import settings_errors, xml_errors
from steuerbote.ustva import Period

DOCTYPE = "VAT Return Extension"

DRAFT = "Entwurf"
CALCULATED = "Berechnet"
READY = "Bereit"
FILED = "Abgegeben"

DECEMBER = 12
# The yes fields only the Anmeldung der Sondervorauszahlung carries.
SONDERVORAUSZAHLUNG_FLAGS = ("is_correction", "no_sepa_mandate", "offset_requested")
# What "Berechnen" finds; another company, year or first month covered discards it.
CALCULATED_VALUES = {
	"kz83": 0,
	"kz39": 0,
	"established_on": None,
	"months_active": 0,
	"computed_base": 0,
	"base": 0,
	"sondervorauszahlung": 0,
	"missing_periods": None,
	"findings": None,
}
FILING_FIELDS = ("filed_via", "filed_on", "transferticket", "filing_note")
# How the form went to the Finanzamt when ELSTER accepted its Senden.
FILED_THROUGH_ERIC = "eric"


class VATReturnExtension(Transmittable, Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from steuerbote.steuerbote.doctype.vat_return_extension_base.vat_return_extension_base import (
			VATReturnExtensionBase,
		)

		amended_from: DF.Link | None
		antrag: DF.Check
		base: DF.Currency
		base_override: DF.Currency
		base_override_reason: DF.SmallText | None
		base_rows: DF.Table[VATReturnExtensionBase]
		company: DF.Link
		computed_base: DF.Currency
		context: DF.Literal["", "Dauerfristverlaengerung", "Umsatzsteuersondervorauszahlung"]
		crediting_period_label: DF.Data | None
		deadline: DF.Date | None
		established_on: DF.Date | None
		filed_on: DF.Date | None
		filed_via: DF.Literal["", "mein_elster", "other_way", "eric"]
		filing_note: DF.SmallText | None
		findings: DF.SmallText | None
		first_month: DF.Int
		first_period_label: DF.Data | None
		is_correction: DF.Check
		kz39: DF.Currency
		kz500_begruendung: DF.SmallText | None
		kz83: DF.Currency
		missing_periods: DF.SmallText | None
		months_active: DF.Int
		naming_series: DF.Literal["DFV-.{year}.-.#####"]
		no_sepa_mandate: DF.Check
		offset_requested: DF.Check
		remarks: DF.SmallText | None
		rhythm: DF.Literal["", "monthly", "quarterly"]
		sondervorauszahlung: DF.Currency
		status: DF.Literal["Entwurf", "Berechnet", "Bereit", "Abgegeben"]
		supplementary_code: DF.Literal["", "1", "2", "3", "4"]
		transferticket: DF.Data | None
		transmission_in_progress: DF.Check
		year: DF.Int
	# end: auto-generated types

	def before_insert(self) -> None:
		"""A new form starts as a draft: an amendment copies the calculation and the filing of the form it
		amends."""
		self._discard_calculation()
		for field in FILING_FIELDS:
			self.set(field, None)

	def onload(self) -> None:
		self.set_onload("elster", self.elster_state())
		self.set_onload("elster_run", self.latest_run())

	def validate(self) -> None:
		self.refuse_changes_while_transmitting()
		if not self.company or self.year is None:
			return  # the mandatory check that follows names the missing field
		self._set_form(settings_for(self.company))
		self._refuse_second_form()
		self._require_correction_of_a_filed_form()
		self._discard_calculation_of_another_form()
		self._set_sondervorauszahlung()
		self._set_status(self._check_form())

	def before_submit(self) -> None:
		sent = None if self.flags.filed_outside else self.accepted_send()
		if not (self.flags.filed_outside or sent):
			frappe.throw(
				_(
					"A Dauerfristverlängerung is filed through Senden or by noting its filing in Mein ELSTER or outside Steuerbote, not by Buchen alone."
				)
			)
		self._check_fit_for_filing()
		if sent:
			self.update(
				{
					"filed_via": FILED_THROUGH_ERIC,
					"filed_on": getdate(sent.finished_at),
					"transferticket": sent.transferticket,
					"filing_note": None,
				}
			)
		self.status = FILED

	def on_submit(self) -> None:
		self._write_prepayment()

	def before_cancel(self) -> None:
		if not self._with_sondervorauszahlung():
			frappe.throw(
				_(
					"{0} is filed with the Finanzamt and cannot be cancelled: an Antrag auf Dauerfristverlängerung without Sondervorauszahlung cannot be corrected."
				).format(self.name)
			)

	@frappe.whitelist(methods=["POST"])
	def calculate(self) -> None:
		"""Berechnen: read the VAT Returns filed for the previous year and the start of the company, and save
		the form with the base, Kz 38 and the deadline."""
		frappe.has_permission(DOCTYPE, "write", self, throw=True)
		if self.docstatus != 0:
			frappe.throw(_("Only a draft form can be calculated."))
		settings = settings_for(self.company)
		self._set_form(settings)
		if self._with_sondervorauszahlung():
			self._read_base(settings)
		self.status = CALCULATED
		self.flags.calculating = True
		try:
			self.save()
		finally:
			self.flags.calculating = False

	@frappe.whitelist(methods=["POST"])
	def mark_filed_outside(
		self,
		filed_via: str = OTHER_WAY,
		note: str | None = None,
		transferticket: str | None = None,
		filed_on: str | None = None,
	) -> str:
		"""In Mein ELSTER eingetragen, or Als außerhalb abgegeben vermerken: the form went to the Finanzamt by
		hand in Mein ELSTER or another way. Submits it with the note how and when it was filed, and with the
		Transferticket if there is one, and returns the name of the ELSTER Transmission that records it."""
		self.check_permission("submit")
		note = (note or "").strip()
		ticket = (transferticket or "").strip()
		if filed_via not in FILED_VIA:
			frappe.throw(_("Steuerbote knows no way of filing {0}.").format(escape_html(str(filed_via))))
		if filed_via == OTHER_WAY and not note:
			frappe.throw(_("Note how and when the form was filed."))
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
			frappe.throw(_("Only a draft form can be marked as filed."))
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
			}
		)
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

	def nutzdaten(self, hersteller_id: str) -> str:
		"""The Nutzdaten for ERiC: form USt 1 H as the form holds it, with the Hersteller-ID in Kz 09."""
		with xml_errors(_("ELSTER Transmission")), self._form_errors():
			filer = vat_return_bridge.filer(settings_for(self.company))
			return ust1h_xml.to_nutzdaten(filer, bridge.form(self), getdate(), hersteller_id)

	def check_transmittable(self) -> None:
		"""A calculated draft of a year whose form and schema Steuerbote knows."""
		if self.docstatus != 0:
			frappe.throw(_("Only a draft form can be transmitted."))
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the form before transmitting it."))
		with xml_errors(_("ELSTER Transmission")), self._form_errors():
			layout_for(cint(self.year))
			ustva_xml.schema_for(cint(self.year))

	def check_can_be_sent(self) -> None:
		"""Senden files the form, once: it needs the form fit for filing and no earlier filing of the year."""
		self._check_fit_for_filing()
		sent = self.filings()
		if sent and sent[0].status == UNKNOWN:
			frappe.throw(
				_(
					"Whether {0} reached ELSTER is unknown. Check in Mein ELSTER whether the form arrived: if it did, note it with Entered in Mein ELSTER; if not, a System Manager deletes {0}, then the form can be sent again."
				).format(sent[0].name)
			)
		if sent:
			frappe.throw(
				_("This form was transmitted already with Transferticket {0}.").format(sent[0].transferticket)
			)
		self._refuse_second_filing()

	def _check_fit_for_filing(self) -> None:
		if self.status not in (CALCULATED, READY):
			frappe.throw(_("Calculate the form before filing it."))
		if self.status != READY and not (self.remarks or "").strip():
			frappe.throw(
				_(
					"The form is not ready, see the open points. Explain in the remarks why it is filed nonetheless."
				)
			)

	def _refuse_second_filing(self) -> None:
		"""The Finanzamt keeps every form filed for the year, also one sent through Steuerbote whose outcome is
		unknown or that was cancelled since: a further form is a corrected Anmeldung (Kz 10), and the Antrag alone
		cannot be corrected (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 8.5.1)."""
		if cint(self.is_correction):
			return
		others = frappe.get_all(
			DOCTYPE,
			filters={"company": self.company, "year": cint(self.year), "name": ["!=", self.name]},
			pluck="name",
		)
		sent = filings(DOCTYPE, others)
		if sent:
			frappe.throw(
				_(
					"{0} filed {1} for {2} already, which the Finanzamt keeps: a further form for the year is a corrected Anmeldung der Sondervorauszahlung (Kz 10)."
				).format(self.company, sent[0].document, cint(self.year))
			)

	def _set_form(self, settings: Document) -> None:
		"""Form, rhythm, deadline and the period crediting the Sondervorauszahlung, from the settings and the
		core: a quarterly filer whose Dauerfristverlängerung holds on files nothing."""
		year = cint(self.year)
		antrag = bool(cint(self.antrag))
		if antrag and not 1 <= cint(self.first_month) <= DECEMBER:
			frappe.throw(_("With the Antrag, enter the first month it covers, 1 to 12."))
		month = cint(self.first_month) if antrag else 1
		rhythm = settings.rhythm_for(year, month)
		first_period = Period.containing(date(year, month, 1), rhythm) if antrag else None
		holidays = holiday_list.holidays(self.company)
		obligation = dauerfrist.obligation(year, rhythm, first_period, holidays)
		if obligation is None:
			frappe.throw(
				_(
					"Filing quarterly, {0} applies for the Dauerfristverlängerung once, and it holds on: nothing is due for {1}. Tick the Antrag in the year the company applies."
				).format(self.company, year)
			)
		with_sondervorauszahlung = obligation.context.with_sondervorauszahlung
		crediting_period = _crediting_period(settings, year) if with_sondervorauszahlung else None
		self.update(
			{
				"rhythm": rhythm.value,
				"context": obligation.context.value,
				"first_period_label": first_period.label if first_period else None,
				"deadline": obligation.deadline,
				"crediting_period_label": crediting_period,
			}
		)
		if not with_sondervorauszahlung:
			self.update(dict.fromkeys(SONDERVORAUSZAHLUNG_FLAGS, 0))

	def _read_base(self, settings: Document) -> None:
		"""The filed VAT Returns of the previous year, the start of the company and the periods the base lacks."""
		year = cint(self.year)
		began = dauerfrist_sources.date_of_establishment(self.company)
		with self._base_errors(began):
			active = bridge.activity(year, began)
		returns, missing = (), ()
		if not active.this_year:
			returns = dauerfrist_sources.filed_returns(self.company, year - 1)
			first_month = began.month if began and began.year == year - 1 else 1
			with settings_errors():
				missing = bridge.gaps(settings.get_period_rules(), year - 1, returns, first_month)
		self.set("base_rows", bridge.base_rows(returns))
		self.update(
			{
				"established_on": began,
				"months_active": active.months,
				"missing_periods": ", ".join(period.label for period in missing) or None,
			}
		)

	def _refuse_second_form(self) -> None:
		others = frappe.get_all(
			DOCTYPE,
			filters={
				"company": self.company,
				"year": cint(self.year),
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
			pluck="name",
		)
		if others:
			frappe.throw(
				_("{0} has a Dauerfristverlängerung for {1} already: {2}.").format(
					self.company, cint(self.year), others[0]
				)
			)

	def _require_correction_of_a_filed_form(self) -> None:
		"""The Finanzamt keeps every form filed for the year, also one cancelled in Steuerbote since, so a further
		form goes to it as a corrected Anmeldung (Kz 10), whether it amends the filed form or is made anew."""
		if cint(self.is_correction):
			return
		if self.amended_from:
			frappe.throw(
				_(
					"{0} amends {1}, which is filed with the Finanzamt: mark it as a corrected Anmeldung (Kz 10)."
				).format(self.name, self.amended_from)
			)
		filed = frappe.get_all(
			DOCTYPE,
			filters={
				"company": self.company,
				"year": cint(self.year),
				"name": ["!=", self.name or ""],
				"filed_via": ["is", "set"],
			},
			order_by="creation desc",
			pluck="name",
		)
		if filed:
			frappe.throw(
				_(
					"{0} filed {1} for {2} already, which the Finanzamt keeps: a further form for the year is a corrected Anmeldung der Sondervorauszahlung (Kz 10)."
				).format(self.company, filed[0], cint(self.year))
			)

	def _discard_calculation_of_another_form(self) -> None:
		before = self.get_doc_before_save()
		if before and not self.flags.calculating and _form_key(before) != _form_key(self):
			self._discard_calculation()

	def _discard_calculation(self) -> None:
		self.set("base_rows", [])
		self.update({**CALCULATED_VALUES, "status": DRAFT})

	def _check_form(self) -> str | None:
		"""Refuse what form USt 1 H does not take. A year whose form Steuerbote does not know yet is an open
		point instead, since the form can still be entered in Mein ELSTER by hand."""
		try:
			layout_for(cint(self.year))
		except FormError as error:
			return _(error.template).format(*error.values)
		with self._form_errors():
			bridge.form(self)
		return None

	@contextmanager
	def _form_errors(self) -> Iterator[None]:
		"""Show a form that ELSTER does not take as a message in the language of the user."""
		try:
			yield
		except FormError as error:
			frappe.throw(_(error.template).format(*error.values))

	def _set_sondervorauszahlung(self) -> None:
		"""Base and Kz 38 from the table of the base and the base by hand, through the core."""
		began = getdate(self.established_on) if self.established_on else None
		with self._base_errors(began):
			override = bridge.override_of(self.base_override, self.base_override_reason)
			if self.status not in (CALCULATED, READY) or not self._with_sondervorauszahlung():
				return
			active = bridge.activity(cint(self.year), began)
			kz83, kz39 = bridge.base_amounts(self.base_rows)
			result = bridge.sondervorauszahlung(kz83, kz39, active, override)
		self.update(
			{
				"kz83": result.kz83,
				"kz39": result.kz39,
				"months_active": active.months,
				"computed_base": result.computed_base or 0,
				"base": result.base,
				"sondervorauszahlung": result.kz38,
			}
		)

	def _set_status(self, finding: str | None) -> None:
		"""A calculated form is ready without open points: the form of its year is known and, without a base by
		hand, no Voranmeldung of the previous year is missing from the base."""
		if self.status not in (CALCULATED, READY):
			self.findings = None
			return
		findings = [finding] if finding else []
		if self._with_sondervorauszahlung() and self.missing_periods and not self._has_override():
			findings.append(
				_(
					"Kz 83 of {0} is missing from the base. File these VAT Returns or set their filing period in the VAT Return Settings and calculate again, or enter the base by hand with the reason."
				).format(self.missing_periods)
			)
		self.findings = "\n".join(findings) or None
		self.status = CALCULATED if findings else READY

	def _write_prepayment(self) -> None:
		"""The row of the year in the VAT Return Settings: the Dauerfristverlängerung holds, and the last
		Voranmeldung of the year deducts the Sondervorauszahlung filed in Kz 39, as
		vat_return.bridge.sondervorauszahlung_values does."""
		settings = settings_for(self.company)
		year = cint(self.year)
		row = next((row for row in settings.prepayments if cint(row.year) == year), None)
		if row is None:
			row = settings.append("prepayments", {"year": year})
		row.dauerfristverlaengerung = 1
		if self._with_sondervorauszahlung():
			row.sondervorauszahlung = vat_return_bridge.to_amount(self.sondervorauszahlung)
		settings.save()

	def _with_sondervorauszahlung(self) -> bool:
		return self.context == Context.UMSATZSTEUERSONDERVORAUSZAHLUNG.value

	def _has_override(self) -> bool:
		return bool((self.base_override_reason or "").strip())

	@contextmanager
	def _base_errors(self, began: date | None) -> Iterator[None]:
		"""Show a base that cannot be computed as a message in the language of the user."""
		try:
			yield
		except bridge.BaseError as error:
			year = cint(self.year)
			messages = {
				bridge.BaseProblem.NO_RETURNS: _(
					"No VAT Return of {0} is filed for {1}. Enter the base by hand, with the reason."
				).format(year - 1, self.company),
				bridge.BaseProblem.EXPECTED_NEEDED: _(
					"{0} began on {1}: its Sondervorauszahlung is the average Vorauszahlung of a month it expects in {2}. Enter the Vorauszahlungen it expects for the year as the base by hand, with the reason."
				).format(self.company, formatdate(began), year),
				bridge.BaseProblem.MISSING_REASON: _("The base by hand needs a reason."),
				bridge.BaseProblem.BEGAN_LATER: _("{0} began on {1}, after {2}.").format(
					self.company, formatdate(began), year
				),
			}
			frappe.throw(messages[error.problem])
		except ValueError as error:
			frappe.throw(str(error))


def _form_key(doc: Document) -> tuple:
	"""What makes a form another one: company, year and, with the Antrag, the first month it covers."""
	antrag = cint(doc.get("antrag"))
	return (doc.get("company"), cint(doc.get("year")), antrag, cint(doc.get("first_month")) if antrag else 0)


def _crediting_period(settings: Document, year: int) -> str | None:
	"""The last Voranmeldungszeitraum of the year in the rhythm of December, None if December has none."""
	try:
		rhythm = rules.rhythm_for(settings.get_period_rules(), year, DECEMBER)
	except rules.SettingsError:
		return None
	return dauerfrist.crediting_period(year, rhythm).label
