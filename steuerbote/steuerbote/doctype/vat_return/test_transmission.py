"""Prüfen, Testsenden, Senden, the notes of a filing outside Steuerbote and the filing state of a period.

The XML of steuerbote.elster, the header, the store of certificate and password and the simulation run for
real; FakeEric of steuerbote/tests/transmitting.py stands in for an installed ERiC. With the stub of the ERiC
library, which the CI builds, a runtime installs from an archive and the worker sends through it.
"""

import base64
import hashlib
import json
import shutil
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.desk.form.meta import get_meta as get_form_meta
from frappe.desk.notifications import get_open_count
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

import steuerbote
from steuerbote.eric import runtime as eric_runtime
from steuerbote.eric import secrets, service
from steuerbote.eric.datenart import ustva
from steuerbote.eric.header import EnvelopeHeader
from steuerbote.eric.result import (
	ERROR,
	HINT,
	UNKNOWN_MESSAGE,
	Message,
	Operation,
	Outcome,
	TransmissionResult,
)
from steuerbote.eric.service import PrivacyNoticeNotConfirmed, WorkerOutput
from steuerbote.eric.tests import stub
from steuerbote.steuerbote.doctype.elster_transmission.transmission import stash_certificate
from steuerbote.steuerbote.doctype.eric_settings.eric_settings import eric_log_root, run_installation
from steuerbote.steuerbote.doctype.vat_return import transmission_adapter
from steuerbote.steuerbote.doctype.vat_return.vat_return import VATReturn
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	make_user,
	post_journal_entry,
)
from steuerbote.tests.transmitting import (
	CERTIFICATE,
	DATENLIEFERANT,
	IS_JOB_ENQUEUED,
	JOB,
	PIN,
	PROTOCOL,
	RUNTIME,
	TICKET,
	TRANSMISSION,
	FakeEric,
	Transmitting,
)

COMPANY = "Steuerbote Test Uebermittlung GmbH"
# Files through the ERiC stub, with periods of its own.
STUB_COMPANY = "Steuerbote Test ERiC-Stub GmbH"
# The filing state of its periods, in TestFilingState.
FILING_COMPANY = "Steuerbote Test Abgabestand GmbH"
DATENLIEFERANT_ADDRESS = {
	"filer_name": COMPANY,
	"street": "Hauptstraße 1",
	"postal_code": "80331",
	"city": "München",
}
ACCOUNTS_USER = "steuerbote-uebermittlung@example.com"
# The form of TransferTicketSType in headerbasis_datentypen.xsd, invented.
MEIN_ELSTER_TICKET = "ab123cdefghijkmnopqrstuvwxyz0123"
NOTE = "Am 9. Oktober 2026 von der Steuerberatung abgegeben"
STUB_TICKET = "et0stub0accepted0000000000000001"
STUB_LIB = "ERiC-44.3.6.0/Linux-x86_64/lib"

ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"8338": ("Erlöse Drittland nicht steuerbar", "Income"),
	"3123": ("Sonstige Leistungen EU 19 %", "Expense"),
	"1787": ("Umsatzsteuer nach § 13b UStG 19 %", "Liability"),
	"1577": ("Vorsteuer nach § 13b UStG 19 %", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1200": ("Bank", "Asset"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}


class TransmissionTestCase(Transmitting, IntegrationTestCase):
	"""A company that files monthly, with ERiC Settings that simulate unless use_runtime() sets them up."""

	company = COMPANY
	abbr = "STUEB"
	accounts: ClassVar[Mapping[str, tuple[str, str]]] = MappingProxyType({})

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(cls.company, cls.abbr)
		cls.account = {
			number: make_account(cls.company, number, name, root_type)
			for number, (name, root_type) in cls.accounts.items()
		}
		make_settings(
			cls.company, [(2026, "monthly", 1)], **{**DATENLIEFERANT_ADDRESS, "filer_name": cls.company}
		)
		make_mapping(cls.company)
		make_user(ACCOUNTS_USER, "Accounts User")

	def new_return(self, period: int, company: str | None = None, **fields):
		return frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": company or self.company,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": period,
				**fields,
			}
		).insert()

	def calculated(self, period: int, **fields):
		doc = self.new_return(period, **fields)
		doc.calculate()
		doc.reload()
		return doc


class TestTransmission(TransmissionTestCase):
	accounts = ACCOUNTS

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		a = cls.account
		march = "2026-03-10"
		post_journal_entry(COMPANY, march, [(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)])
		post_journal_entry(COMPANY, march, [(a["1400"], 2000, 0), (a["8336"], 0, 2000)])
		post_journal_entry(COMPANY, march, [(a["1400"], 500, 0), (a["8338"], 0, 500)])
		post_journal_entry(
			COMPANY, march, [(a["3123"], 300, 0), (a["1577"], 57, 0), (a["1787"], 0, 57), (a["1200"], 0, 300)]
		)
		post_journal_entry(COMPANY, march, [(a["1576"], 95, 0), (a["1200"], 0, 95)])
		make_company(STUB_COMPANY, "STUES")
		make_settings(
			STUB_COMPANY, [(2026, "monthly", 1)], **{**DATENLIEFERANT_ADDRESS, "filer_name": STUB_COMPANY}
		)
		make_mapping(STUB_COMPANY)

	def test_pruefen_in_the_simulation_records_the_result_and_leaves_the_return_as_it_is(self):
		doc = self.calculated(3)
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
				transmission.transferticket,
				transmission.testmerker,
				transmission.user,
			),
			(
				"VAT Return",
				doc.name,
				COMPANY,
				"validate",
				"Erfolgreich",
				"valid",
				1,
				"simulation",
				None,
				None,
				"Administrator",
			),
		)
		self.assertIn("SIM-000", self.codes(transmission))
		self.assertLessEqual(transmission.started_at, transmission.finished_at)
		operation, nutzdaten, header, runtime_info, certificate, password = run.call_args.args
		self.assertEqual(
			(operation, runtime_info, certificate, password), (Operation.VALIDATE, None, None, None)
		)
		self.assertEqual(
			header,
			EnvelopeHeader(
				hersteller_id="00000",
				datenlieferant=COMPANY,
				produkt_name="steuerbote",
				produkt_version=steuerbote.__version__,
				empfaenger="9123",
				datenart_version="UStVA_2026",
				testmerker=None,
				nutzdaten_ticket="1",
			),
		)
		for element in (
			"<Zeitraum>03</Zeitraum>",
			"<Steuernummer>9123045678901</Steuernummer>",
			"<Kz09>00000</Kz09>",
			"<Kz81>1000</Kz81>",
			"<Kz67>57.00</Kz67>",
			"<Kz83>95.00</Kz83>",
		):
			with self.subTest(element=element):
				self.assertIn(element, nutzdaten)
		xml = self.attachment(transmission, "xml")
		self.assertEqual((xml.file_url, xml.is_private), (transmission.xml, 1))
		self.assertEqual(xml.get_content(), nutzdaten)
		self.assertFalse(transmission.protocol_pdf or transmission.response_xml)
		self.assertEqual(
			publish.call_args.args,
			(
				"steuerbote_elster_transmission",
				{
					"document_type": "VAT Return",
					"document": doc.name,
					"transmission": transmission.name,
					"operation": "validate",
					"status": "Erfolgreich",
					"simulated": 1,
				},
			),
		)
		self.assertEqual(publish.call_args.kwargs, {"user": "Administrator", "after_commit": True})

	def test_testsenden_in_the_simulation_needs_no_certificate_and_keeps_the_return_a_draft(self):
		doc = self.calculated(1)
		transmission, _, _ = self.transmitted(doc, "test_send")
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.simulated, transmission.testmerker),
			("Erfolgreich", "accepted", 1, "700000004"),
		)
		self.assertTrue(transmission.transferticket.startswith("SIM-"))
		protocol = self.attachment(transmission, "protocol_pdf")
		self.assertTrue(protocol.get_content().startswith(b"%PDF"))
		self.assertEqual((doc.docstatus, doc.status), (0, "Bereit"))

	def test_senden_is_not_offered_in_the_simulation(self):
		doc = self.calculated(2)
		with patch("frappe.enqueue") as enqueue, self.assertRaisesRegex(frappe.ValidationError, "simulation"):
			doc.transmit("send")
		enqueue.assert_not_called()
		self.assertFalse(
			frappe.db.exists(TRANSMISSION, {"document_type": "VAT Return", "document": doc.name})
		)

	def test_an_unknown_operation_is_refused(self):
		doc = self.calculated(2)
		with patch("frappe.enqueue") as enqueue, self.assertRaises(frappe.ValidationError):
			doc.transmit("delete")
		enqueue.assert_not_called()

	def test_senden_needs_the_permission_to_submit(self):
		self.use_runtime()
		doc = self.calculated(2)
		with self.set_user(ACCOUNTS_USER), patch("frappe.enqueue") as enqueue:
			with self.assertRaises(frappe.PermissionError):
				doc.transmit("send", "token")
			doc.transmit("validate")
		self.assertEqual(enqueue.call_count, 1)

	def test_senden_files_the_return_and_keeps_the_transferticket(self):
		self.use_runtime()
		doc = self.calculated(4)
		fake = FakeEric()
		transmission, _, _ = self.transmitted(doc, "send", fake, self.stash(doc))
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (1, "Abgegeben", 0))
		self.assertEqual(
			(
				transmission.status,
				transmission.outcome,
				transmission.simulated,
				transmission.transferticket,
				transmission.testmerker,
				transmission.eric_version,
			),
			("Erfolgreich", "accepted", 0, TICKET, None, "44.3.6.0"),
		)
		log_dir = eric_log_root() / transmission.name
		self.assertEqual(fake.detections, [(ustva(2026), Operation.SEND, "12345", log_dir)])
		(run,) = fake.runs
		self.assertEqual((run["certificate"], run["password"]), (CERTIFICATE, PIN))
		self.assertEqual(run["runtime"], replace(RUNTIME, hersteller_id="12345", log_dir=log_dir))
		self.assertEqual(
			(run["header"].hersteller_id, run["header"].datenlieferant, run["header"].testmerker),
			("12345", DATENLIEFERANT, None),
		)
		self.assertIn("<Kz09>12345</Kz09>", run["nutzdaten"])
		self.assertEqual(self.attachment(transmission, "protocol_pdf").get_content(), PROTOCOL)
		with self.assertRaises(secrets.SecretsExpired):
			self.handed_over(transmission.name, doc)

	def test_the_certificate_and_its_password_reach_the_job_only_through_its_transmission(self):
		self.use_runtime()
		doc = self.calculated(10)
		fake = FakeEric()
		token = self.stash(doc)
		name, enqueue = self.transmit(doc, "test_send", token)
		(call,) = enqueue.call_args_list
		self.assertEqual(call.args, (JOB,))
		self.assertNotIn(token, repr(call))
		self.assertEqual(
			call.kwargs,
			{
				"name": doc.name,
				"operation": "test_send",
				"transmission": name,
				"queue": "long",
				"timeout": 300,
				"job_id": f"steuerbote:elster:{name}",
				"enqueue_after_commit": True,
			},
		)
		self.run_job(enqueue, fake)
		transmission = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual((transmission.testmerker, transmission.simulated), ("700000004", 0))
		self.assertEqual(fake.runs[0]["header"].testmerker, "700000004")
		self.assertEqual(fake.detections[0][1], Operation.TEST_SEND)
		recorded = frappe.as_json(transmission.as_dict())
		self.assertNotIn(PIN, recorded)
		self.assertNotIn(base64.b64encode(CERTIFICATE).decode(), recorded)

	def test_testsenden_needs_the_certificate_outside_the_simulation(self):
		self.use_runtime()
		doc = self.calculated(12)
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "certificate"),
		):
			doc.transmit("test_send")
		enqueue.assert_not_called()

	def test_a_certificate_that_is_gone_starts_no_run_and_ends_one_that_waits_for_it(self):
		self.use_runtime()
		doc = self.calculated(10)
		# The request that is refused rolls back what it wrote.
		frappe.db.savepoint("refused")
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "certificate"),
		):
			doc.transmit("test_send", "x" * 43)
		frappe.db.rollback(save_point="refused")
		enqueue.assert_not_called()
		self.assertFalse(frappe.db.exists(TRANSMISSION, {"document": doc.name, "operation": "test_send"}))
		name, enqueue = self.transmit(doc, "test_send", self.stash(doc))
		secrets.discard(name)
		fake = FakeEric()
		publish, _ = self.run_job(enqueue, fake)
		transmission = frappe.get_doc(TRANSMISSION, name)
		doc.reload()
		self.assertEqual(
			(transmission.status, transmission.outcome, doc.transmission_in_progress),
			("Fehlgeschlagen", "failed", 0),
		)
		self.assertIn("certificate", transmission.messages[-1].text)
		self.assertEqual(fake.runs, [])
		self.assertEqual(publish.call_args.args[1]["status"], "Fehlgeschlagen")

	def test_data_the_xml_does_not_take_end_in_a_failed_transmission(self):
		doc = self.calculated(1)
		street = frappe.db.get_value("VAT Return Settings", COMPANY, "street")
		frappe.db.set_value("VAT Return Settings", COMPANY, "street", None)
		self.addCleanup(frappe.db.set_value, "VAT Return Settings", COMPANY, "street", street)
		transmission, _, run = self.transmitted(doc, "validate")
		self.assertEqual((transmission.status, doc.transmission_in_progress), ("Fehlgeschlagen", 0))
		self.assertIn("street of the Datenlieferant", transmission.messages[-1].text)
		run.assert_not_called()
		self.assertEqual((doc.docstatus, doc.status), (0, "Bereit"))

	def test_a_rejected_send_keeps_the_return_a_draft_with_the_messages(self):
		self.use_runtime()
		doc = self.calculated(5)
		error = Message("610101210", "Die Steuernummer ist ungültig.", ERROR, "Steuernummer")
		fake = FakeEric(outcome=Outcome.REJECTED, messages=(error,))
		transmission, _, _ = self.transmitted(doc, "send", fake, self.stash(doc))
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (0, "Bereit", 0))
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.transferticket),
			("Fehlgeschlagen", "rejected", None),
		)
		self.assertEqual(
			[(row.code, row.severity, row.text, row.field) for row in transmission.messages],
			[("610101210", "error", "Die Steuernummer ist ungültig.", "Steuernummer")],
		)

	def test_a_send_that_may_have_reached_elster_blocks_sending_until_it_is_cleared(self):
		self.use_runtime()
		doc = self.calculated(12)
		lost = Message("SB-WORKER", "ERiC hat nach 120 Sekunden nicht geantwortet.", ERROR)
		fake = FakeEric(outcome=Outcome.UNKNOWN, messages=(lost, UNKNOWN_MESSAGE))
		transmission, publish, _ = self.transmitted(doc, "send", fake, self.stash(doc))
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.transferticket),
			("Unbekannt", "unknown", None),
		)
		self.assertEqual(self.codes(transmission), ["SB-WORKER", "SB-UNKNOWN"])
		self.assertEqual((doc.docstatus, publish.call_args.args[1]["status"]), (0, "Unbekannt"))
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(
				frappe.ValidationError, f"Whether {transmission.name} reached ELSTER"
			):
				doc.transmit("send", self.stash(doc))
			other = self.calculated(12)
			with self.assertRaisesRegex(frappe.ValidationError, "transmitted already"):
				other.transmit("send", self.stash(other))
		enqueue.assert_not_called()
		frappe.delete_doc(TRANSMISSION, transmission.name)
		_, enqueue = self.transmit(doc, "send", self.stash(doc))
		self.assertEqual(enqueue.call_args.kwargs["operation"], "send")

	def test_a_sent_return_that_could_not_be_submitted_is_never_sent_again(self):
		self.use_runtime()
		doc = self.calculated(6)
		fake = FakeEric()
		with patch.object(VATReturn, "before_submit", side_effect=frappe.ValidationError("Kaputt")):
			transmission, _, _ = self.transmitted(doc, "send", fake, self.stash(doc))
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (0, "Bereit", 0))
		self.assertEqual((transmission.status, transmission.transferticket), ("Erfolgreich", TICKET))
		self.assertEqual(transmission.messages[-1].severity, "error")
		self.assertIn(TICKET, transmission.messages[-1].text)
		self.assertIn("Kaputt", transmission.messages[-1].text)
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "transmitted already"):
				doc.transmit("send", self.stash(doc))
			other = self.calculated(6)
			with self.assertRaisesRegex(frappe.ValidationError, "transmitted already"):
				other.transmit("send", self.stash(other))
		enqueue.assert_not_called()

	def test_a_corrected_return_replaces_the_return_sent_before(self):
		self.use_runtime()
		first = self.calculated(7)
		fake = FakeEric()
		self.transmitted(first, "send", fake, self.stash(first))
		correction = self.calculated(7, is_correction=1)
		self.transmitted(correction, "send", fake, self.stash(correction))
		first.reload()
		self.assertEqual((first.status, correction.docstatus, correction.status), ("Ersetzt", 1, "Abgegeben"))
		self.assertIn("<Kz10>1</Kz10>", fake.runs[1]["nutzdaten"])

	def test_one_transmission_at_a_time(self):
		doc = self.calculated(8)
		name, _ = self.transmit(doc, "validate")
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "transmission_in_progress"), 1)
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

	def test_a_check_whose_job_is_gone_is_closed_as_failed(self):
		doc = self.calculated(8)
		first, _ = self.transmit(doc, "validate")
		with patch(IS_JOB_ENQUEUED, return_value=False):
			second, enqueue = self.transmit(doc, "validate")
		enqueue.assert_called_once()
		stale = frappe.get_doc(TRANSMISSION, first)
		self.assertEqual((stale.status, stale.outcome), ("Fehlgeschlagen", "failed"))
		self.assertTrue(stale.finished_at)
		self.assertIn("Nothing reached ELSTER", stale.messages[-1].text)
		self.assertEqual(frappe.db.get_value(TRANSMISSION, second, "status"), "Läuft")

	def test_a_send_whose_job_is_gone_has_an_unknown_outcome_and_is_not_repeated(self):
		self.use_runtime()
		doc = self.calculated(11)
		first, _ = self.transmit(doc, "send", self.stash(doc))
		with (
			patch(IS_JOB_ENQUEUED, return_value=False),
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, f"Whether {first} reached ELSTER"),
		):
			doc.transmit("send", self.stash(doc))
		enqueue.assert_not_called()
		self.assertEqual(
			frappe.db.get_value(TRANSMISSION, first, ["status", "outcome"]), ("Unbekannt", "unknown")
		)

	def test_only_a_calculated_draft_is_transmitted(self):
		draft = self.new_return(5)
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "Calculate"):
				draft.transmit("validate")
			filed = self.calculated(5)
			filed.mark_filed_outside(NOTE)
			with self.assertRaisesRegex(frappe.ValidationError, "draft"):
				filed.transmit("validate")
		enqueue.assert_not_called()

	def test_marking_as_filed_outside_records_the_note_and_files_the_return(self):
		doc = self.calculated(9)
		note = "Am 9. Oktober 2026 in Mein ELSTER übermittelt"
		name = doc.mark_filed_outside(note)
		self.assertEqual(
			frappe.db.get_value(TRANSMISSION, name, ["filed_via", "filed_on"]), ("other_way", None)
		)
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status), (1, "Abgegeben"))
		transmission = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual(
			(
				transmission.document_type,
				transmission.document,
				transmission.operation,
				transmission.status,
				transmission.simulated,
				transmission.remarks,
				transmission.user,
			),
			("VAT Return", doc.name, "extern", "Erfolgreich", 0, note, "Administrator"),
		)
		with self.assertRaisesRegex(frappe.ValidationError, "draft"):
			doc.mark_filed_outside(note)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(TRANSMISSION, name)

	def test_marking_as_filed_outside_needs_a_note_and_a_calculation(self):
		doc = self.new_return(12)
		with self.assertRaisesRegex(frappe.ValidationError, "how and when"):
			doc.mark_filed_outside("  ")
		with self.assertRaisesRegex(frappe.ValidationError, "Calculate"):
			doc.mark_filed_outside("In Mein ELSTER übermittelt")
		self.assertFalse(
			frappe.db.exists(TRANSMISSION, {"document_type": "VAT Return", "document": doc.name})
		)
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "docstatus"), 0)

	def test_the_return_lists_its_transmissions_and_confirmations_under_its_connections(self):
		doc = self.calculated(2)
		first, _, _ = self.transmitted(doc, "validate")
		second, _, _ = self.transmitted(doc, "test_send")
		data = frappe.get_meta("VAT Return").get_dashboard_data()
		self.assertEqual(
			(data.fieldname, data.dynamic_links, data.non_standard_fieldnames),
			(
				"document",
				{"document": ["VAT Return", "document_type"]},
				{"VAT ID Confirmation": "vat_return"},
			),
		)
		self.assertEqual(
			[group["items"] for group in data.transactions],
			[["ELSTER Transmission"], ["VAT ID Confirmation"]],
		)
		(links,) = (
			links
			for links in get_open_count("VAT Return", doc.name)["count"]["external_links_found"]
			if links["doctype"] == TRANSMISSION
		)
		self.assertEqual(links["count"], 2)
		self.assertEqual(
			sorted(frappe.get_all(TRANSMISSION, filters={"document": doc.name}, pluck="name")),
			sorted([first.name, second.name]),
		)

	def test_the_form_brings_the_dialog_the_transmissions_share(self):
		script = get_form_meta("VAT Return", cached=False).get("__js")
		self.assertIn("function ask_for_certificate(frm, operation, title, texts) {", script)
		self.assertIn("add_transmission_buttons(frm, group, return_texts());", script)
		self.assertNotIn("{% include", script)

	def test_a_transmission_names_a_document_that_files_through_eric(self):
		transmission = frappe.get_doc(
			{
				"doctype": TRANSMISSION,
				"document_type": "Company",
				"document": COMPANY,
				"company": COMPANY,
				"operation": "validate",
				"status": "Läuft",
			}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "no document of type Company"):
			transmission.insert(ignore_permissions=True)

	def test_a_transmission_stays_as_it_was_recorded(self):
		doc = self.calculated(1)
		transmission, _, _ = self.transmitted(doc, "validate")
		transmission.transferticket = "et-geaendert"
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be changed"):
			transmission.save()
		with self.assertRaises(frappe.LinkExistsError):
			frappe.delete_doc("VAT Return", doc.name)
		frappe.delete_doc(TRANSMISSION, transmission.name)
		self.assertFalse(frappe.db.exists(TRANSMISSION, transmission.name))

	def test_stashing_keeps_certificate_and_password_behind_a_token(self):
		doc = self.new_return(2)
		encoded = base64.b64encode(CERTIFICATE).decode()
		token = stash_certificate(doc.doctype, doc.name, encoded, PIN)
		secrets.hand_over(
			token, "ELSTER-2026-99999", user=frappe.session.user, document=(doc.doctype, doc.name)
		)
		self.assertEqual(self.handed_over("ELSTER-2026-99999", doc), (CERTIFICATE, PIN))
		with self.assertRaises(secrets.SecretsExpired):
			self.handed_over("ELSTER-2026-99999", doc)
		for certificate, password, message in (
			("", PIN, "certificate file"),
			("kein base64!", PIN, "certificate file"),
			(encoded, "kurz", "6 to 128"),
			(encoded, "x" * 129, "6 to 128"),
			(encoded, "Passwört-2026", "6 to 128"),
		):
			with (
				self.subTest(certificate=certificate[:8], password=len(password)),
				self.assertRaisesRegex(frappe.ValidationError, message) as raised,
			):
				stash_certificate(doc.doctype, doc.name, certificate, password)
			self.assertNotIn(password, str(raised.exception))

	def test_the_form_learns_whether_eric_is_simulated(self):
		doc = self.new_return(3)
		doc.run_method("onload")
		self.assertEqual(
			doc.get_onload("elster"), {"simulation": True, "stale": False, "sent": False, "locked": None}
		)
		self.use_runtime()
		doc.run_method("onload")
		self.assertEqual(
			doc.get_onload("elster"), {"simulation": False, "stale": False, "sent": False, "locked": None}
		)
		self.use_runtime(privacy_notice_confirmed=0)
		doc.run_method("onload")
		self.assertFalse(doc.get_onload("elster")["simulation"])

	def test_the_form_learns_the_senden_after_which_the_draft_stays_as_it_was_sent(self):
		"""refuse_if_sent keeps all but the remarks of a draft whose real Senden ELSTER accepted or left
		unknown. The form hides what it refuses and names that Senden: by its Transferticket, or by its ELSTER
		Transmission while the outcome is unknown. A Testsenden goes to no Finanzamt, and a filed return is no
		draft."""
		frappe.db.savepoint("sent_returns")
		self.addCleanup(frappe.db.rollback, save_point="sent_returns")
		tested, unknown, accepted = (self.calculated(3) for _ in range(3))
		tested.new_transmission("test_send", simulated=False, status="Erfolgreich", transferticket=TICKET)
		lost = unknown.new_transmission("send", simulated=False, status="Unbekannt")
		sent = accepted.new_transmission("send", simulated=False, status="Erfolgreich", transferticket=TICKET)
		for doc, locked in (
			(tested, None),
			(unknown, {"transmission": lost.name, "status": "Unbekannt", "transferticket": None}),
			(accepted, {"transmission": sent.name, "status": "Erfolgreich", "transferticket": TICKET}),
		):
			doc.run_method("onload")
			with self.subTest(doc=doc.name):
				self.assertEqual(doc.get_onload("elster")["locked"], locked)
		accepted.submit()
		accepted.run_method("onload")
		self.assertIsNone(accepted.get_onload("elster")["locked"])

	def test_the_form_names_the_errors_and_hints_of_the_latest_run(self):
		"""ERiC's hints never stop a check (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.2.4.1), so the form of the
		return counts them with the errors of its latest finished run and shows the first of each kind."""
		self.use_runtime()
		doc = self.calculated(3)
		doc.run_method("onload")
		self.assertIsNone(doc.get_onload("elster_run"))
		hints = tuple(Message(f"1108513{index}", f"Hinweis {index}", HINT) for index in range(4))
		error = Message("610001002", "Fehler während der Plausibilitätsprüfung.", ERROR)
		failed, _, _ = self.transmitted(
			doc, "validate", FakeEric(outcome=Outcome.INVALID, messages=(error, *hints))
		)
		doc.run_method("onload")
		self.assertEqual(
			doc.get_onload("elster_run"),
			{
				"name": failed.name,
				"operation": "validate",
				"status": "Fehlgeschlagen",
				"simulated": 0,
				"errors": 1,
				"hints": 4,
				"first_errors": [{"code": "610001002", "text": "Fehler während der Plausibilitätsprüfung."}],
				"first_hints": [
					{"code": f"1108513{index}", "text": f"Hinweis {index}"} for index in range(3)
				],
			},
		)
		valid, _, _ = self.transmitted(doc, "validate", FakeEric(messages=hints[:1]))
		doc.run_method("onload")
		self.assertEqual(
			{key: doc.get_onload("elster_run")[key] for key in ("name", "status", "errors", "hints")},
			{"name": valid.name, "status": "Erfolgreich", "errors": 0, "hints": 1},
		)
		running, _ = self.transmit(doc, "validate")
		self.assertEqual(frappe.db.get_value(TRANSMISSION, running, "status"), "Läuft")
		doc.run_method("onload")
		self.assertEqual(doc.get_onload("elster_run")["name"], valid.name)

	def install_stub_runtime(self) -> Path:
		"""Install the ERiC stub as runtime 44.3.6.0 from an archive the bench names, with the Hersteller-ID and the
		confirmation in the settings; returns the directory of the runtimes, which the caller patches in."""
		library = stub.library()
		directory = Path(tempfile.mkdtemp(prefix="steuerbote-eric-"))
		self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
		archive = directory / "ERiC-44.3.6.0-Linux-x86_64.jar"
		with zipfile.ZipFile(archive, "w") as jar:
			jar.write(library, f"{STUB_LIB}/libericapi.so")
			jar.writestr(f"{STUB_LIB}/plugins2/libcommonData.so", b"")
			jar.writestr(f"{STUB_LIB}/plugins2/libcheckUStVA_2026.so", b"")
		checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
		root = directory / "eric"
		bench = {"steuerbote_eric_archive": str(archive), "steuerbote_eric_archive_sha256": checksum}
		with (
			patch.object(transmission_adapter, "runtime_root", return_value=root),
			patch.object(transmission_adapter, "common_site_config", return_value=bench),
			patch("frappe.publish_realtime"),
		):
			run_installation()
		settings = frappe.get_single("ERiC Settings")
		self.assertEqual(
			(settings.installed_version, settings.lib_dir), ("44.3.6.0", str(root / "44.3.6.0" / "lib"))
		)
		settings.update(
			{"hersteller_id": "12345", "datenlieferant": DATENLIEFERANT, "privacy_notice_confirmed": 1}
		)
		settings.save()
		return root

	def test_through_the_eric_stub_a_runtime_installs_and_testsenden_and_senden_go_out(self):
		root = self.install_stub_runtime()
		with patch.object(transmission_adapter, "runtime_root", return_value=root):
			doc = self.new_return(1, company=STUB_COMPANY)
			doc.calculate()
			doc.reload()
			test, _, _ = self.transmitted(doc, "test_send", token=self.stash(doc))
			self.assertEqual(
				(test.status, test.outcome, test.simulated, test.transferticket, test.testmerker),
				("Erfolgreich", "accepted", 0, STUB_TICKET, "700000004"),
			)
			self.assertEqual(test.eric_version, "44.3.6.0")
			self.assertTrue((eric_log_root() / test.name).is_dir())
			self.assertEqual((doc.docstatus, doc.status), (0, "Bereit"))
			sent, _, _ = self.transmitted(doc, "send", token=self.stash(doc))
		self.assertEqual(
			(sent.status, sent.outcome, sent.transferticket), ("Erfolgreich", "accepted", STUB_TICKET)
		)
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (1, "Abgegeben", 0))

	def test_through_the_eric_stub_a_runtime_whose_libraries_changed_is_never_loaded(self):
		"""Every run checks the runtime against its manifest first: a library planted after the installation never
		gets loaded, and nothing reaches the worker, certificate and PIN least of all."""
		root = self.install_stub_runtime()
		with (root / "44.3.6.0" / "lib" / "libericapi.so").open("ab") as library:
			library.write(b"planted")
		with (
			patch.object(transmission_adapter, "runtime_root", return_value=root),
			patch.object(service, "start_worker") as start,
		):
			doc = self.new_return(2, company=STUB_COMPANY)
			doc.calculate()
			doc.reload()
			checked, _, _ = self.transmitted(doc, "validate")
			sent, _, _ = self.transmitted(doc, "test_send", token=self.stash(doc))
		start.assert_not_called()
		for transmission in (checked, sent):
			with self.subTest(operation=transmission.operation):
				self.assertEqual((transmission.status, transmission.outcome), ("Fehlgeschlagen", "failed"))
				self.assertIn("verändert: libericapi.so", transmission.messages[-1].text)
				self.assertIn("44.3.6.0", transmission.messages[-1].text)
		self.assertEqual((doc.docstatus, doc.transmission_in_progress), (0, 0))


class TestFilingState(TransmissionTestCase):
	"""Whether a period counts as filed, and how a return gets there. Each test has a month of its own."""

	company = FILING_COMPANY
	abbr = "STUEA"

	def test_a_period_filed_outside_steuerbote_stops_senden_of_another_draft(self):
		self.use_runtime()
		first, second = self.calculated(1), self.calculated(1)
		first.mark_filed_outside(NOTE)
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "filed already as"):
				second.transmit("send", self.stash(second))
			second.transmit("validate")
		self.assertEqual(enqueue.call_count, 1)

	def test_a_period_filed_outside_steuerbote_stops_the_file_for_mein_elster_of_another_draft(self):
		first, second = self.calculated(2), self.calculated(2)
		first.mark_filed_outside(NOTE)
		with self.assertRaisesRegex(frappe.ValidationError, "filed already as"):
			second.make_import_file()
		self.assertTrue(first.make_import_file())

	def test_a_filed_return_cannot_be_cancelled(self):
		outside = self.calculated(3)
		outside.mark_filed_outside(NOTE)
		self.use_runtime()
		sent = self.calculated(4)
		self.transmitted(sent, "send", FakeEric(), self.stash(sent))
		for doc in (outside, sent):
			doc.reload()
			with (
				self.subTest(doc=doc.name),
				self.assertRaisesRegex(frappe.ValidationError, "cannot be cancelled"),
			):
				doc.cancel()
			self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "docstatus"), 1)

	def test_a_cancelled_return_that_was_sent_still_stops_senden_without_kz10(self):
		self.use_runtime()
		sent = self.calculated(5)
		self.transmitted(sent, "send", FakeEric(), self.stash(sent))
		# A return cancelled before a filed return could no longer be cancelled.
		frappe.db.set_value("VAT Return", sent.name, "docstatus", 2)
		draft = self.calculated(5)
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "transmitted already as"):
				draft.transmit("send", self.stash(draft))
			correction = self.calculated(5, is_correction=1)
			correction.transmit("send", self.stash(correction))
		self.assertEqual(enqueue.call_args.kwargs["operation"], "send")

	def test_buchen_alone_files_no_return(self):
		doc = self.calculated(6)
		with self.assertRaisesRegex(frappe.ValidationError, "not by Buchen alone"):
			doc.submit()
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, ["docstatus", "status"]), (0, "Bereit"))

	def test_a_sent_return_that_could_not_be_submitted_is_submitted_with_buchen(self):
		self.use_runtime()
		doc = self.calculated(7)
		with patch.object(VATReturn, "before_submit", side_effect=frappe.ValidationError("Kaputt")):
			transmission, _, _ = self.transmitted(doc, "send", FakeEric(), self.stash(doc))
		self.assertEqual((transmission.status, doc.docstatus), ("Erfolgreich", 0))
		doc.run_method("onload")
		self.assertTrue(doc.get_onload("elster")["sent"])
		with self.assertRaisesRegex(frappe.ValidationError, "submit it with Buchen"):
			doc.mark_filed_outside(NOTE)
		doc.submit()
		self.assertEqual(
			frappe.db.get_value("VAT Return", doc.name, ["docstatus", "status"]), (1, "Abgegeben")
		)

	def test_in_mein_elster_abgegeben_records_transferticket_and_date(self):
		doc = self.calculated(8)
		name = doc.mark_filed_outside(
			filed_via="mein_elster", transferticket=f" {MEIN_ELSTER_TICKET} ", filed_on="2026-09-08"
		)
		doc.reload()
		self.assertEqual((doc.docstatus, doc.status), (1, "Abgegeben"))
		transmission = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual(
			(
				transmission.operation,
				transmission.status,
				transmission.filed_via,
				transmission.transferticket,
				getdate(transmission.filed_on),
				transmission.remarks or "",
			),
			("extern", "Erfolgreich", "mein_elster", MEIN_ELSTER_TICKET, date(2026, 9, 8), ""),
		)

	def test_the_note_of_a_filing_is_checked(self):
		doc = self.calculated(9)
		for values, message in (
			({"filed_via": "other_way"}, "how and when"),
			({"remarks": NOTE, "filed_via": "fax"}, "way of filing"),
			({"filed_via": "mein_elster", "transferticket": "et12"}, "no Transferticket"),
			({"filed_via": "mein_elster", "filed_on": add_days(today(), 1)}, "in the future"),
		):
			with self.subTest(values=values), self.assertRaisesRegex(frappe.ValidationError, message):
				doc.mark_filed_outside(**values)
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "docstatus"), 0)
		self.assertFalse(
			frappe.db.exists(TRANSMISSION, {"document_type": "VAT Return", "document": doc.name})
		)

	def test_the_form_releases_a_lock_whose_job_is_gone(self):
		self.use_runtime()
		doc = self.calculated(10)
		name, job = self.transmit(doc, "send", self.stash(doc))
		doc.reload()
		with patch(IS_JOB_ENQUEUED, return_value=True) as enqueued:
			doc.run_method("onload")
		enqueued.assert_called_with(f"steuerbote:elster:{name}")
		self.assertFalse(doc.get_onload("elster")["stale"])
		with patch(IS_JOB_ENQUEUED, return_value=False):
			doc.run_method("onload")
			self.assertTrue(doc.get_onload("elster")["stale"])
			doc.release_stale_transmission()
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "transmission_in_progress"), 0)
		stale = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual((stale.status, stale.outcome), ("Unbekannt", "unknown"))
		self.assertIn("Mein ELSTER", stale.messages[-1].text)
		doc.reload()
		doc.run_method("onload")
		self.assertFalse(doc.get_onload("elster")["stale"])
		doc.remarks = "Nach der gelösten Sperre"
		doc.save()
		fake = FakeEric()
		self.run_job(job, fake)
		self.assertEqual(fake.runs, [])
		with self.assertRaises(secrets.SecretsExpired):
			self.handed_over(name, doc)

	def test_a_job_whose_transmission_was_closed_does_nothing(self):
		doc = self.calculated(11)
		first, first_job = self.transmit(doc, "validate")
		with patch(IS_JOB_ENQUEUED, return_value=False):
			doc.release_stale_transmission()
			second, second_job = self.transmit(doc, "validate")
		self.assertNotEqual(first_job.call_args.kwargs["job_id"], second_job.call_args.kwargs["job_id"])
		fake = FakeEric()
		self.run_job(first_job, fake)
		self.assertEqual(fake.runs, [])
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "transmission_in_progress"), 1)
		self.assertEqual(frappe.db.get_value(TRANSMISSION, first, "status"), "Fehlgeschlagen")
		self.assertEqual(frappe.db.get_value(TRANSMISSION, second, "status"), "Läuft")
		self.run_job(second_job)
		self.assertEqual(frappe.db.get_value(TRANSMISSION, second, "status"), "Erfolgreich")
		self.assertEqual(frappe.db.get_value("VAT Return", doc.name, "transmission_in_progress"), 0)

	def test_eric_needs_the_confirmed_datenschutzhinweise_the_simulation_does_not(self):
		doc = self.calculated(12)
		simulated, _, _ = self.transmitted(doc, "validate")
		self.assertEqual(simulated.status, "Erfolgreich")
		self.use_runtime(privacy_notice_confirmed=0)
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "Datenschutzhinweise"),
		):
			doc.transmit("validate")
		enqueue.assert_not_called()
		self.use_runtime()
		name, enqueue = self.transmit(doc, "validate")
		self.use_runtime(privacy_notice_confirmed=0)
		fake = FakeEric()
		self.run_job(enqueue, fake)
		self.assertEqual(fake.runs, [])
		transmission = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual(transmission.status, "Fehlgeschlagen")
		self.assertIn("Datenschutzhinweise", transmission.messages[-1].text)

	def test_pruefen_and_testsenden_take_a_beta_only_without_a_released_runtime_senden_never(self):
		released = replace(RUNTIME, version="44.3.6.0")
		beta = replace(RUNTIME, version="45.1.5.0")
		log_dir = Path("/srv/eric/log")
		for installed, expected in (
			(
				(released, beta),
				{Operation.VALIDATE: released, Operation.TEST_SEND: released, Operation.SEND: released},
			),
			((beta,), {Operation.VALIDATE: beta, Operation.TEST_SEND: beta, Operation.SEND: None}),
		):

			def detect(
				root,
				*,
				datenart,
				allow_beta,
				log_dir,
				hersteller_id,
				confirmed_privacy_notice,
				installed=installed,
			):
				found = [info for info in installed if allow_beta or info is not beta]
				return replace(found[0], log_dir=log_dir, hersteller_id=hersteller_id) if found else None

			for operation, runtime_info in expected.items():
				with (
					self.subTest(installed=len(installed), operation=operation),
					patch.object(eric_runtime, "detect", side_effect=detect),
				):
					found = transmission_adapter.detect_runtime(ustva(2026), operation, "12345", log_dir)
					self.assertEqual(found and found.version, runtime_info and runtime_info.version)

	def test_the_runtime_carries_the_confirmation_without_which_the_service_runs_no_eric(self):
		header = EnvelopeHeader(
			hersteller_id="12345",
			datenlieferant=DATENLIEFERANT,
			produkt_name="steuerbote",
			produkt_version=steuerbote.__version__,
			empfaenger="9198",
			datenart_version="UStVA_2026",
			testmerker=None,
			nutzdaten_ticket="1",
		)
		checked = TransmissionResult(Operation.VALIDATE, True, False, RUNTIME.version, None, None)
		answer = WorkerOutput(0, json.dumps(checked.to_dict()).encode(), "")

		def detect(root, *, datenart, allow_beta, log_dir, hersteller_id, confirmed_privacy_notice):
			return replace(
				RUNTIME,
				log_dir=log_dir,
				hersteller_id=hersteller_id,
				confirmed_privacy_notice=confirmed_privacy_notice,
			)

		for confirmed in (0, 1):
			self.use_runtime(privacy_notice_confirmed=confirmed)
			with (
				self.subTest(confirmed=confirmed),
				patch.object(eric_runtime, "detect", side_effect=detect),
				patch.object(service, "start_worker") as start,
				patch.object(service, "wait_for", return_value=answer),
			):
				runtime_info = transmission_adapter.detect_runtime(
					ustva(2026), Operation.VALIDATE, "12345", Path("/srv/eric/log")
				)
				self.assertIs(runtime_info.confirmed_privacy_notice, bool(confirmed))
				if confirmed:
					result = transmission_adapter.run(
						Operation.VALIDATE, "<Anmeldungssteuern/>", header, runtime_info, None, None
					)
					self.assertIs(result.outcome, Outcome.VALID)
					start.assert_called_once()
				else:
					with self.assertRaisesRegex(PrivacyNoticeNotConfirmed, "Datenschutzhinweise"):
						transmission_adapter.run(
							Operation.VALIDATE, "<Anmeldungssteuern/>", header, runtime_info, None, None
						)
					start.assert_not_called()
