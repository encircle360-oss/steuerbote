"""Prüfen, Testsenden and Senden of the Dauerfristverlängerung through ERiC, as for the VAT Return
(elster_transmission/transmission.py), with form USt 1 H as the Nutzdaten (steuerbote.elster.ust1h_xml).

FakeEric of steuerbote/tests/transmitting.py stands in for an installed ERiC; without it the simulation answers,
which checks the XML against the schema of the year when the ERiC documentation is at hand.
"""

from datetime import date
from unittest.mock import patch

import frappe
from frappe.desk.form.meta import get_meta as get_form_meta
from frappe.desk.notifications import get_open_count
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from steuerbote.dauerfrist import form as dauerfrist_form
from steuerbote.eric import secrets
from steuerbote.eric.datenart import ustva
from steuerbote.eric.result import ERROR, HINT, UNKNOWN_MESSAGE, Message, Operation, Outcome
from steuerbote.steuerbote.doctype.vat_return_extension.test_vat_return_extension import (
	money,
	prepayments,
	remove,
)
from steuerbote.steuerbote.doctype.vat_return_extension.vat_return_extension import VATReturnExtension
from steuerbote.steuerbote.print_format.umsatzsteuer_voranmeldung.test_umsatzsteuer_voranmeldung import cells
from steuerbote.tests.helpers import make_company, make_settings, make_user
from steuerbote.tests.transmitting import (
	CERTIFICATE,
	IS_JOB_ENQUEUED,
	PIN,
	PROTOCOL,
	TICKET,
	TRANSMISSION,
	FakeEric,
	Transmitting,
)

# The companies are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "VAT Return"]

DOCTYPE = "VAT Return Extension"
PRINT_FORMAT = "Dauerfristverlängerung"
SVZ = "Umsatzsteuersondervorauszahlung"
DF = "Dauerfristverlaengerung"
# Files monthly from 2026. Its Anmeldung der Sondervorauszahlung 2026 takes a base by hand of 44.000 €, so that
# Kz 38 is 4.000 € and the form is ready.
COMPANY = "Steuerbote Test DFV-Übermittlung GmbH"
BASE_BY_HAND = {"base_override": 44000, "base_override_reason": "Voranmeldungen 2025 im Altsystem"}
# Files quarterly from 2026 and applies for the Dauerfristverlängerung from January 2026.
QUARTERLY_COMPANY = "Steuerbote Test DFV-Antrag GmbH"
ADDRESS = {"street": "Hauptstraße 1", "postal_code": "80331", "city": "München"}
ACCOUNTS_USER = "steuerbote-dfv-uebermittlung@example.com"
# The form of TransferTicketSType in headerbasis_datentypen.xsd, invented.
MEIN_ELSTER_TICKET = "ab123cdefghijkmnopqrstuvwxyz0123"
LOST = Message("SB-WORKER", "ERiC hat nach 120 Sekunden nicht geantwortet.", ERROR)


def discard(name: str) -> None:
	"""Take a form out with its ELSTER Transmissions: deleting the form frees its name for the next one."""
	frappe.db.delete(TRANSMISSION, {"document_type": DOCTYPE, "document": name})
	remove(name)


class TestExtensionTransmission(Transmitting, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "SDUE")
		make_settings(COMPANY, [(2026, "monthly", 1)], filer_name=COMPANY, **ADDRESS)
		make_company(QUARTERLY_COMPANY, "SDUA")
		make_settings(QUARTERLY_COMPANY, [(2026, "quarterly", 1)], filer_name=QUARTERLY_COMPANY, **ADDRESS)
		make_user(ACCOUNTS_USER, "Accounts User")

	def form(self, company: str = COMPANY, year: int = 2026, **fields):
		doc = frappe.get_doc({"doctype": DOCTYPE, "company": company, "year": year, **fields}).insert()
		self.addCleanup(discard, doc.name)
		return doc

	def calculated(self, company: str = COMPANY, year: int = 2026, **fields):
		"""The Anmeldung der Sondervorauszahlung of COMPANY, or with QUARTERLY_COMPANY its Antrag, calculated."""
		values = (
			{**BASE_BY_HAND, **fields} if company == COMPANY else {"antrag": 1, "first_month": 1, **fields}
		)
		doc = self.form(company, year, **values)
		doc.calculate()
		doc.reload()
		return doc

	def test_pruefen_in_the_simulation_checks_the_anmeldung_and_leaves_the_form_as_it_is(self):
		doc = self.calculated()
		self.assertEqual(
			(doc.context, doc.status, money(doc.sondervorauszahlung)), (SVZ, "Bereit", money(4000))
		)
		transmission, publish, run = self.transmitted(doc, "validate")
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (0, "Bereit", 0))
		self.assertEqual(
			(
				transmission.document_type,
				transmission.document,
				transmission.company,
				transmission.operation,
				transmission.status,
				transmission.outcome,
				transmission.simulated,
				transmission.eric_version,
			),
			(DOCTYPE, doc.name, COMPANY, "validate", "Erfolgreich", "valid", 1, "simulation"),
		)
		self.assertIn("SIM-000", self.codes(transmission))
		operation, nutzdaten, header, runtime_info, certificate, password = run.call_args.args
		self.assertEqual(
			(operation, runtime_info, certificate, password), (Operation.VALIDATE, None, None, None)
		)
		self.assertEqual(
			(header.datenart_version, header.empfaenger, header.hersteller_id, header.testmerker),
			("UStVA_2026", "9123", "00000", None),
		)
		for element in (
			"<Umsatzsteuersondervorauszahlung>",
			"<Jahr>2026</Jahr>",
			"<Steuernummer>9123045678901</Steuernummer>",
			"<Kz09>00000</Kz09>",
			"<Kz38>4000</Kz38>",
		):
			with self.subTest(element=element):
				self.assertIn(element, nutzdaten)
		self.assertNotIn("Umsatzsteuervoranmeldung", nutzdaten)
		self.assertEqual(self.attachment(transmission, "xml").get_content(), nutzdaten)
		self.assertEqual(
			publish.call_args.args,
			(
				"steuerbote_elster_transmission",
				{
					"document_type": DOCTYPE,
					"document": doc.name,
					"transmission": transmission.name,
					"operation": "validate",
					"status": "Erfolgreich",
					"simulated": 1,
				},
			),
		)

	def test_pruefen_in_the_simulation_checks_the_provisional_form_of_2027_in_its_datenart(self):
		doc = self.calculated(year=2027)
		self.assertEqual((doc.context, doc.status, doc.provisional), (SVZ, "Berechnet", 1))
		transmission, _, run = self.transmitted(doc, "validate")
		self.assertEqual((transmission.status, transmission.outcome), ("Erfolgreich", "valid"))
		operation, nutzdaten, header, *_ = run.call_args.args
		self.assertEqual((operation, header.datenart_version), (Operation.VALIDATE, "UStVA_2027"))
		for element in (
			'<Anmeldungssteuern xmlns="http://finkonsens.de/elster/elsteranmeldung/ustva/v2027" version="2027">',
			"<Jahr>2027</Jahr>",
			"<Kz09>00000</Kz09>",
			"<Kz38>4000</Kz38>",
		):
			with self.subTest(element=element):
				self.assertIn(element, nutzdaten)

	def test_the_antrag_of_a_quarterly_filer_goes_as_the_context_dauerfristverlaengerung(self):
		doc = self.calculated(QUARTERLY_COMPANY)
		self.assertEqual((doc.context, doc.status), (DF, "Bereit"))
		transmission, _, run = self.transmitted(doc, "validate")
		nutzdaten = run.call_args.args[1]
		self.assertEqual(transmission.status, "Erfolgreich")
		self.assertIn("<Dauerfristverlaengerung>", nutzdaten)
		self.assertIn("<Kz09>00000</Kz09>", nutzdaten)
		self.assertNotIn("Kz38", nutzdaten)

	def test_testsenden_in_the_simulation_keeps_the_form_a_draft_with_a_placeholder_protocol(self):
		doc = self.calculated()
		transmission, _, _ = self.transmitted(doc, "test_send")
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.simulated, transmission.testmerker),
			("Erfolgreich", "accepted", 1, "700000004"),
		)
		self.assertTrue(transmission.transferticket.startswith("SIM-"))
		protocol = self.attachment(transmission, "protocol_pdf").get_content()
		self.assertIn(b"Vordruck: Anmeldung der Sondervorauszahlung 2026", protocol)
		self.assertIn(b"Kennzahl 38: 4000", protocol)
		self.assertEqual((doc.docstatus, doc.status, doc.filed_via), (0, "Bereit", None))

	def test_senden_is_not_offered_in_the_simulation(self):
		doc = self.calculated()
		with patch("frappe.enqueue") as enqueue, self.assertRaisesRegex(frappe.ValidationError, "simulation"):
			doc.transmit("send")
		enqueue.assert_not_called()
		self.assertFalse(frappe.db.exists(TRANSMISSION, {"document_type": DOCTYPE, "document": doc.name}))

	def test_senden_files_the_form_with_its_transferticket_and_writes_kz38_into_the_settings(self):
		self.use_runtime()
		doc = self.calculated()
		fake = FakeEric()
		transmission, _, _ = self.transmitted(doc, "send", fake, self.stash(doc))
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (1, "Abgegeben", 0))
		self.assertEqual(
			(doc.filed_via, getdate(doc.filed_on), doc.transferticket, doc.filing_note),
			("eric", getdate(transmission.finished_at), TICKET, None),
		)
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.transferticket, transmission.testmerker),
			("Erfolgreich", "accepted", TICKET, None),
		)
		(run,) = fake.runs
		self.assertEqual((run["certificate"], run["password"]), (CERTIFICATE, PIN))
		self.assertEqual(
			(run["header"].hersteller_id, run["header"].datenart_version, run["header"].testmerker),
			("12345", "UStVA_2026", None),
		)
		self.assertIn("<Kz09>12345</Kz09>", run["nutzdaten"])
		self.assertEqual(fake.detections[0][:3], (ustva(2026), Operation.SEND, "12345"))
		self.assertEqual(self.attachment(transmission, "protocol_pdf").get_content(), PROTOCOL)
		self.assertIn((2026, 1, money(4000)), prepayments(COMPANY))
		with self.assertRaises(secrets.SecretsExpired):
			self.handed_over(transmission.name, doc)
		printed = cells(frappe.get_print(DOCTYPE, doc.name, print_format=PRINT_FORMAT, no_letterhead=1))
		self.assertIn("Abgegeben über | ERiC |", printed)
		self.assertIn(f"Transferticket | {TICKET} |", printed)

	def test_senden_needs_the_permission_to_submit(self):
		self.use_runtime()
		doc = self.calculated()
		with self.set_user(ACCOUNTS_USER), patch("frappe.enqueue") as enqueue:
			with self.assertRaises(frappe.PermissionError):
				doc.transmit("send", "token")
			doc.transmit("validate")
		self.assertEqual(enqueue.call_count, 1)

	def test_senden_needs_a_ready_form_or_remarks(self):
		self.use_runtime()
		doc = self.calculated()
		frappe.db.set_value(DOCTYPE, doc.name, "status", "Berechnet")
		with patch("frappe.enqueue") as enqueue, self.assertRaisesRegex(frappe.ValidationError, "not ready"):
			doc.transmit("send", self.stash(doc))
		enqueue.assert_not_called()
		frappe.db.set_value(DOCTYPE, doc.name, "remarks", "Abgestimmt mit der Steuerberatung")
		_, enqueue = self.transmit(doc, "send", self.stash(doc))
		self.assertEqual(enqueue.call_args.kwargs["operation"], "send")

	def test_only_a_calculated_draft_of_a_known_form_is_transmitted(self):
		year = dauerfrist_form.LATEST_YEAR + 1
		draft = self.form(**BASE_BY_HAND)
		unknown = self.form(year=year, **BASE_BY_HAND)
		unknown.calculate()
		unknown.reload()
		filed = self.calculated(QUARTERLY_COMPANY)
		filed.mark_filed_outside(filed_via="mein_elster")
		filed.reload()
		for doc, message in (
			(draft, "Calculate the form before transmitting it"),
			(unknown, f"does not know form USt 1 H for {year}"),
			(filed, "Only a draft form can be transmitted"),
		):
			with (
				self.subTest(doc=doc.name),
				patch("frappe.enqueue") as enqueue,
				self.assertRaisesRegex(frappe.ValidationError, message),
			):
				doc.transmit("validate")
			enqueue.assert_not_called()

	def test_a_send_that_may_have_reached_elster_blocks_sending_until_it_is_cleared(self):
		self.use_runtime()
		doc = self.calculated()
		fake = FakeEric(outcome=Outcome.UNKNOWN, messages=(LOST, UNKNOWN_MESSAGE))
		transmission, publish, _ = self.transmitted(doc, "send", fake, self.stash(doc))
		self.assertEqual(
			(transmission.status, transmission.outcome, doc.docstatus, publish.call_args.args[1]["status"]),
			("Unbekannt", "unknown", 0, "Unbekannt"),
		)
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, f"Whether {transmission.name} reached ELSTER"),
		):
			doc.transmit("send", self.stash(doc))
		enqueue.assert_not_called()
		frappe.delete_doc(TRANSMISSION, transmission.name)
		_, enqueue = self.transmit(doc, "send", self.stash(doc))
		self.assertEqual(enqueue.call_args.kwargs["operation"], "send")

	def test_a_form_sent_for_the_year_leaves_a_further_one_to_a_corrected_anmeldung(self):
		self.use_runtime()
		sent = self.calculated()
		fake = FakeEric(outcome=Outcome.UNKNOWN, messages=(LOST, UNKNOWN_MESSAGE))
		self.transmitted(sent, "send", fake, self.stash(sent))
		# A form cancelled before a filed one could no longer be cancelled.
		frappe.db.set_value(DOCTYPE, sent.name, "docstatus", 2)
		further = self.calculated()
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, f"{COMPANY} filed {sent.name} for 2026 already"),
		):
			further.transmit("send", self.stash(further))
		enqueue.assert_not_called()
		with self.assertRaisesRegex(frappe.ValidationError, f"{COMPANY} filed {sent.name} for 2026 already"):
			further.mark_filed_outside(filed_via="mein_elster")
		further.reload()
		further.is_correction = 1
		further.save()
		_, enqueue = self.transmit(further, "send", self.stash(further))
		self.assertEqual(enqueue.call_args.kwargs["operation"], "send")

	def test_a_form_elster_accepted_while_its_submission_failed_is_submitted_with_buchen(self):
		self.use_runtime()
		doc = self.calculated()
		with patch.object(VATReturnExtension, "before_submit", side_effect=frappe.ValidationError("Kaputt")):
			transmission, _, _ = self.transmitted(doc, "send", FakeEric(), self.stash(doc))
		self.assertEqual(
			(transmission.status, transmission.transferticket, doc.docstatus), ("Erfolgreich", TICKET, 0)
		)
		self.assertIn("Kaputt", transmission.messages[-1].text)
		self.assertIn(TICKET, transmission.messages[-1].text)
		doc.run_method("onload")
		self.assertTrue(doc.get_onload("elster")["sent"])
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "transmitted already"),
		):
			doc.transmit("send", self.stash(doc))
		enqueue.assert_not_called()
		with self.assertRaisesRegex(frappe.ValidationError, "submit it with Buchen"):
			doc.mark_filed_outside(filed_via="mein_elster")
		doc.reload()
		doc.submit()
		self.assertEqual(
			(doc.docstatus, doc.status, doc.filed_via, doc.transferticket), (1, "Abgegeben", "eric", TICKET)
		)

	def test_buchen_alone_files_no_form(self):
		doc = self.calculated()
		with self.assertRaisesRegex(frappe.ValidationError, "not by Buchen alone"):
			doc.submit()

	def test_an_anmeldung_sent_through_eric_is_corrected_by_amending_it_with_kz10(self):
		self.use_runtime()
		doc = self.calculated()
		self.transmitted(doc, "send", FakeEric(), self.stash(doc))
		doc.cancel()
		amendment = frappe.copy_doc(doc)
		amendment.update({"amended_from": doc.name, "docstatus": 0})
		with self.assertRaisesRegex(frappe.ValidationError, "mark it as a corrected Anmeldung"):
			amendment.insert()
		amendment.is_correction = 1
		amendment.insert()
		self.addCleanup(discard, amendment.name)
		amendment.calculate()
		amendment.reload()
		_, enqueue = self.transmit(amendment, "send", self.stash(amendment))
		self.assertEqual(enqueue.call_args.kwargs["operation"], "send")

	def test_one_transmission_at_a_time(self):
		doc = self.calculated()
		name, _ = self.transmit(doc, "validate")
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "transmission_in_progress"), 1)
		self.assertEqual(frappe.db.get_value(TRANSMISSION, name, "status"), "Läuft")
		with (
			patch(IS_JOB_ENQUEUED, return_value=True),
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "running"),
		):
			doc.transmit("validate")
		enqueue.assert_not_called()
		doc.reload()
		doc.remarks = "Geändert während der Übermittlung"
		with self.assertRaisesRegex(frappe.ValidationError, "running"):
			doc.save()
		doc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "running"):
			doc.calculate()
		doc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "running"):
			doc.mark_filed_outside(filed_via="mein_elster")

	def test_the_form_releases_a_lock_whose_job_is_gone(self):
		self.use_runtime()
		doc = self.calculated()
		name, job = self.transmit(doc, "send", self.stash(doc))
		doc.reload()
		with patch(IS_JOB_ENQUEUED, return_value=False):
			doc.run_method("onload")
			self.assertTrue(doc.get_onload("elster")["stale"])
			doc.release_stale_transmission()
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "transmission_in_progress"), 0)
		stale = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual((stale.status, stale.outcome), ("Unbekannt", "unknown"))
		self.assertIn(doc.name, stale.messages[-1].text)
		doc.reload()
		doc.remarks = "Nach der gelösten Sperre"
		doc.save()
		fake = FakeEric()
		self.run_job(job, fake)
		self.assertEqual(fake.runs, [])
		with self.assertRaises(secrets.SecretsExpired):
			self.handed_over(name, doc)

	def test_filing_outside_steuerbote_is_recorded_as_an_elster_transmission(self):
		doc = self.calculated()
		name = doc.mark_filed_outside(
			filed_via="mein_elster", transferticket=MEIN_ELSTER_TICKET, filed_on="2026-02-09"
		)
		transmission = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual(
			(
				transmission.document_type,
				transmission.document,
				transmission.operation,
				transmission.status,
				transmission.simulated,
				transmission.filed_via,
				transmission.transferticket,
				getdate(transmission.filed_on),
			),
			(
				DOCTYPE,
				doc.name,
				"extern",
				"Erfolgreich",
				0,
				"mein_elster",
				MEIN_ELSTER_TICKET,
				date(2026, 2, 9),
			),
		)
		doc.reload()
		self.assertEqual(
			(doc.docstatus, doc.filed_via, doc.transferticket), (1, "mein_elster", MEIN_ELSTER_TICKET)
		)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(TRANSMISSION, name)

	def test_the_form_learns_whether_eric_is_simulated(self):
		doc = self.form(**BASE_BY_HAND)
		doc.run_method("onload")
		self.assertEqual(
			doc.get_onload("elster"),
			{
				"simulation": True,
				"stale": False,
				"sent": False,
				"locked": None,
				"printout": "Übertragungsprotokoll",
			},
		)
		self.use_runtime()
		doc.run_method("onload")
		self.assertEqual(
			doc.get_onload("elster"),
			{
				"simulation": False,
				"stale": False,
				"sent": False,
				"locked": None,
				"printout": "Übertragungsprotokoll",
			},
		)

	def test_the_form_names_the_errors_and_hints_of_its_latest_run(self):
		"""As on the VAT Return: hints never stop a check (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.2.4.1)."""
		doc = self.calculated()
		doc.run_method("onload")
		self.assertIsNone(doc.get_onload("elster_run"))
		hint = Message("610001003", "Hinweise während der Plausibilitätsprüfung.", HINT)
		transmission, _, _ = self.transmitted(doc, "validate", FakeEric(messages=(hint,)))
		doc.run_method("onload")
		self.assertEqual(
			doc.get_onload("elster_run"),
			{
				"name": transmission.name,
				"operation": "validate",
				"status": "Erfolgreich",
				"simulated": 1,
				"errors": 0,
				"hints": 1,
				"first_errors": [],
				"first_hints": [{"code": "610001003", "text": "Hinweise während der Plausibilitätsprüfung."}],
			},
		)
		self.assertIn("show_latest_run(frm);", get_form_meta(DOCTYPE, cached=False).get("__js"))

	def test_the_form_lists_its_transmissions_under_its_connections(self):
		doc = self.calculated()
		self.transmitted(doc, "validate")
		self.transmitted(doc, "test_send")
		data = frappe.get_meta(DOCTYPE).get_dashboard_data()
		self.assertEqual(
			(data.fieldname, data.dynamic_links, [group["items"] for group in data.transactions]),
			("document", {"document": [DOCTYPE, "document_type"]}, [[TRANSMISSION]]),
		)
		(links,) = get_open_count(DOCTYPE, doc.name)["count"]["external_links_found"]
		self.assertEqual((links["doctype"], links["count"]), (TRANSMISSION, 2))

	def test_the_form_brings_the_dialog_the_transmissions_share(self):
		script = get_form_meta(DOCTYPE, cached=False).get("__js")
		self.assertIn("function ask_for_certificate(frm, operation, title, texts) {", script)
		self.assertIn("add_transmission_buttons(frm, group, form_texts());", script)
		self.assertNotIn("{% include", script)
