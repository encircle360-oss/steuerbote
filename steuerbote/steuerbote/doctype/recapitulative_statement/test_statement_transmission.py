"""Prüfen, Testsenden and Senden of the Zusammenfassende Meldung through ERiC, as for the VAT Return
(elster_transmission/transmission.py), with the Nutzdaten of the Datenart ZMDO (steuerbote.elster.zm_xml).

FakeEric of steuerbote/tests/transmitting.py stands in for an installed ERiC; without it the simulation answers,
which checks the Nutzdaten against zm_000005.xsd when the ERiC documentation is at hand. Every test takes its
statements out again, so that the next one can file the same Meldezeitraum; a test that changes the ledger of a
month has that month to itself.
"""

from datetime import date
from unittest.mock import patch

import frappe
from frappe.desk.form.meta import get_meta as get_form_meta
from frappe.desk.notifications import get_open_count
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, now_datetime

from steuerbote.eric import secrets
from steuerbote.eric.datenart import ZMDO
from steuerbote.eric.result import ERROR, HINT, UNKNOWN_MESSAGE, Message, Operation, Outcome
from steuerbote.steuerbote.doctype.recapitulative_statement import recapitulative_statement as controller
from steuerbote.steuerbote.doctype.recapitulative_statement.recapitulative_statement import (
	RecapitulativeStatement,
)
from steuerbote.tests.helpers import (
	insert_record,
	make_account,
	make_company,
	make_customer,
	make_mapping,
	make_settings,
	make_user,
	post_sales_invoice,
)
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

# The companies, their accounts, customers and confirmations are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Account",
	"Address",
	"Company",
	"Customer",
	"DocType",
	"User",
	"VAT ID Confirmation",
]

DOCTYPE = "Recapitulative Statement"
SETTINGS = "VAT Return Settings"
# Files the ZM monthly from January 2026 and delivers to Alpen every month, 1.000 € times the month.
COMPANY = "Steuerbote Test ZM-Übermittlung GmbH"
ABBR = "STZU"
OWN_VAT_ID = "DE123456788"
AUSTRIAN = "ATU12345678"
ALPEN = "Alpen Handel GmbH (ZM-Übermittlung)"
ADDRESS = {"street": "Hauptstraße 1", "postal_code": "80331", "city": "München", "phone": "089 1234567"}
ACCOUNTS = {
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}
ACCOUNTS_USER = "steuerbote-zm-uebermittlung@example.com"
# The form of TransferTicketSType in headerbasis_datentypen.xsd, invented.
MEIN_ELSTER_TICKET = "ab123cdefghijkmnopqrstuvwxyz0123"
LOST = Message("SB-WORKER", "ERiC hat nach 120 Sekunden nicht geantwortet.", ERROR)


def discard(name: str) -> None:
	"""Take a statement out with its ELSTER Transmissions: a filed statement cannot be cancelled, so it leaves the
	database directly, and its Meldezeitraum is free for the next test."""
	frappe.db.delete(TRANSMISSION, {"document_type": DOCTYPE, "document": name})
	if frappe.db.get_value(DOCTYPE, name, "docstatus") == 1:
		frappe.db.set_value(DOCTYPE, name, "docstatus", 2)
	frappe.delete_doc(DOCTYPE, name, force=True)


class TestStatementTransmission(Transmitting, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, ABBR)
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(
			COMPANY,
			[(2026, "monthly", 1)],
			ust_idnr=OWN_VAT_ID,
			zm_rules=[{"year": 2026, "valid_from_month": 1, "rhythm": "monthly", "services_monthly": 1}],
			filer_name=COMPANY,
			**ADDRESS,
		)
		make_mapping(COMPANY)
		make_customer(ALPEN, "Austria", AUSTRIAN, city="Wien")
		for month in range(1, 12):
			cls.deliver(month, 1, 1000 * month)
		# The BZSt confirmed the number of Alpen, so that every statement is ready.
		insert_record(
			"VAT ID Confirmation",
			name=f"USTID-{ABBR}-{AUSTRIAN}",
			requested=AUSTRIAN,
			requester=OWN_VAT_ID,
			company=COMPANY,
			service="bzst",
			outcome="valid",
			result="valid",
			requested_at=now_datetime(),
		)
		make_user(ACCOUNTS_USER, "Accounts User")

	@classmethod
	def deliver(cls, month: int, number: int, amount: int) -> None:
		a = cls.account
		post_sales_invoice(
			COMPANY,
			f"SINV-{ABBR}-{month:02d}-{number}",
			ALPEN,
			f"2026-{month:02d}-{9 + number:02d}",
			[(a["1400"], amount, 0), (a["8125"], 0, amount)],
		)

	def statement(self, month: int, **fields):
		doc = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"company": COMPANY,
				"year": 2026,
				"period_kind": "month",
				"period_index": month,
				**fields,
			}
		).insert()
		self.addCleanup(discard, doc.name)
		return doc

	def calculated(self, month: int, **fields):
		doc = self.statement(month, **fields)
		doc.calculate()
		doc.reload()
		return doc

	def setting(self, **values) -> None:
		"""Values of the VAT Return Settings for one test, written as they are."""
		before = frappe.db.get_value(SETTINGS, COMPANY, list(values), as_dict=True)
		frappe.db.set_value(SETTINGS, COMPANY, values)
		self.addCleanup(frappe.db.set_value, SETTINGS, COMPANY, dict(before))

	def test_pruefen_in_the_simulation_checks_the_zm_and_leaves_the_statement_as_it_is(self):
		doc = self.calculated(1)
		self.assertEqual((doc.status, doc.ready), ("Bereit", 1))
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
		self.assertNotIn("error", [row.severity for row in transmission.messages])
		operation, nutzdaten, header, runtime_info, certificate, password = run.call_args.args
		self.assertEqual(
			(operation, runtime_info, certificate, password), (Operation.VALIDATE, None, None, None)
		)
		self.assertEqual(
			(header.datenart_version, header.empfaenger, header.hersteller_id, header.testmerker),
			("ZMDO", "BF", "00000", None),
		)
		for element in (
			'<zm xmlns="http://www.elster.de/elsterxml/schema/v11" version="000005">',
			"<knri>DE123456788</knri>",
			"<zulnr1>N</zulnr1>",
			"<zulnr2>1111111</zulnr2>",
			f"<name>{COMPANY}</name>",
			"<strasse>Hauptstraße 1</strasse>",
			"<plz>80331</plz>",
			"<ort>München</ort>",
			"<staat>DE</staat>",
			"<telefon>089 1234567</telefon>",
			'<zm-zeilen waehrung="1" meldeart="10">',
			"<anzeige>false</anzeige>",
			"<quart>21</quart>",
			"<jahr>2026</jahr>",
			'<zeile umsatzart="L">',
			f"<knre>{AUSTRIAN}</knre>",
			"<betrag>1000</betrag>",
		):
			with self.subTest(element=element):
				self.assertIn(element, nutzdaten)
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

	def test_testsenden_in_the_simulation_keeps_the_statement_a_draft_with_a_placeholder_protocol(self):
		doc = self.calculated(2)
		transmission, _, _ = self.transmitted(doc, "test_send")
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.simulated, transmission.testmerker),
			("Erfolgreich", "accepted", 1, "700000004"),
		)
		self.assertTrue(transmission.transferticket.startswith("SIM-"))
		protocol = self.attachment(transmission, "protocol_pdf").get_content()
		for line in (b"Datenart: ZMDO", b"Meldezeitraum: 22/2026", b"Meldezeilen: 1"):
			with self.subTest(line=line):
				self.assertIn(line, protocol)
		self.assertEqual((doc.docstatus, doc.status, doc.filed_via or None), (0, "Bereit", None))

	def test_senden_is_not_offered_in_the_simulation(self):
		doc = self.calculated(3)
		with patch("frappe.enqueue") as enqueue, self.assertRaisesRegex(frappe.ValidationError, "simulation"):
			doc.transmit("send")
		enqueue.assert_not_called()
		self.assertFalse(frappe.db.exists(TRANSMISSION, {"document_type": DOCTYPE, "document": doc.name}))

	def test_senden_files_the_statement_with_its_transferticket(self):
		self.use_runtime()
		doc = self.calculated(4)
		fake = FakeEric()
		transmission, _, _ = self.transmitted(doc, "send", fake, self.stash(doc))
		self.assertEqual((doc.docstatus, doc.status, doc.transmission_in_progress), (1, "Abgegeben", 0))
		self.assertEqual(
			(doc.filed_via, getdate(doc.filed_on), doc.transferticket, doc.filing_note, doc.filed_by),
			("eric", getdate(transmission.finished_at), TICKET, None, "Administrator"),
		)
		self.assertEqual(
			(transmission.status, transmission.outcome, transmission.transferticket, transmission.testmerker),
			("Erfolgreich", "accepted", TICKET, None),
		)
		(run,) = fake.runs
		self.assertEqual((run["certificate"], run["password"]), (CERTIFICATE, PIN))
		self.assertEqual(
			(run["header"].hersteller_id, run["header"].datenart_version, run["header"].empfaenger),
			("12345", "ZMDO", "BF"),
		)
		self.assertNotIn(">12345<", run["nutzdaten"])
		self.assertEqual(fake.detections[0][:3], (ZMDO, Operation.SEND, "12345"))
		self.assertEqual(self.attachment(transmission, "protocol_pdf").get_content(), PROTOCOL)
		with self.assertRaises(secrets.SecretsExpired):
			self.handed_over(transmission.name, doc)
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be cancelled"):
			doc.cancel()
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(TRANSMISSION, transmission.name)

	def test_senden_needs_the_permission_to_submit(self):
		self.use_runtime()
		doc = self.calculated(3)
		with self.set_user(ACCOUNTS_USER), patch("frappe.enqueue") as enqueue:
			with self.assertRaises(frappe.PermissionError):
				doc.transmit("send", "token")
			doc.transmit("validate")
		self.assertEqual(enqueue.call_count, 1)

	def test_senden_needs_a_ready_statement_or_remarks(self):
		self.use_runtime()
		doc = self.calculated(3)
		frappe.db.set_value(DOCTYPE, doc.name, {"status": "Berechnet", "ready": 0})
		with patch("frappe.enqueue") as enqueue, self.assertRaisesRegex(frappe.ValidationError, "not ready"):
			doc.transmit("send", self.stash(doc))
		enqueue.assert_not_called()
		frappe.db.set_value(DOCTYPE, doc.name, "remarks", "Die USt-IdNr. ist am Liefertag bestätigt worden.")
		_, enqueue = self.transmit(doc, "send", self.stash(doc))
		self.assertEqual(enqueue.call_args.kwargs["operation"], "send")

	def test_senden_waits_for_berechnen_after_the_ledger_changed(self):
		"""Berechnen reads the ledger once: the lines go to the BZSt only while the ledger books what they were made
		from, as for the file for Mein ELSTER; Prüfen may run."""
		self.use_runtime()
		doc = self.calculated(9)
		self.deliver(9, 2, 500)
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, f"Beleg SINV-{ABBR}-09-2 geht laut Hauptbuch"),
		):
			doc.transmit("send", self.stash(doc))
		enqueue.assert_not_called()
		_, enqueue = self.transmit(doc, "validate")
		self.assertEqual(enqueue.call_args.kwargs["operation"], "validate")

	def test_only_a_calculated_draft_is_transmitted(self):
		draft = self.statement(5)
		with (
			patch("frappe.enqueue"),
			self.assertRaisesRegex(frappe.ValidationError, "Calculate the statement"),
		):
			draft.transmit("validate")
		confirming = self.calculated(5)
		frappe.db.set_value(DOCTYPE, confirming.name, "confirmation_in_progress", 1)
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "are being confirmed"),
		):
			confirming.transmit("validate")
		enqueue.assert_not_called()
		frappe.db.set_value(DOCTYPE, confirming.name, "confirmation_in_progress", 0)
		confirming.reload()
		confirming.mark_filed_outside(filed_via="mein_elster")
		with patch("frappe.enqueue"), self.assertRaisesRegex(frappe.ValidationError, "Only a draft"):
			confirming.transmit("validate")

	def test_a_send_that_may_have_reached_elster_blocks_sending_until_it_is_cleared(self):
		self.use_runtime()
		doc = self.calculated(5)
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

	def test_a_meldezeitraum_sent_through_steuerbote_is_filed_for_every_other_statement(self):
		"""Whether the BZSt has it is open, so no other statement of the Meldezeitraum goes as an Erstmeldung."""
		self.use_runtime()
		sent = self.calculated(6)
		fake = FakeEric(outcome=Outcome.UNKNOWN, messages=(LOST, UNKNOWN_MESSAGE))
		self.transmitted(sent, "send", fake, self.stash(sent))
		other = self.calculated(6, remarks="Zweiter Versuch")
		refused = f"Juni 2026 of {COMPANY} was transmitted already as {sent.name}"
		for attempt in (
			lambda: other.transmit("send", self.stash(other)),
			lambda: other.mark_filed_outside(filed_via="mein_elster"),
			other.make_csv_file,
		):
			with patch("frappe.enqueue") as enqueue, self.assertRaisesRegex(frappe.ValidationError, refused):
				attempt()
			enqueue.assert_not_called()
			other.reload()

	def test_an_accepted_berichtigung_replaces_the_statement_it_corrects(self):
		self.use_runtime()
		filed = self.calculated(8)
		self.transmitted(filed, "send", FakeEric(), self.stash(filed))
		self.assertEqual((filed.docstatus, filed.status, filed.filed_via), (1, "Abgegeben", "eric"))
		self.deliver(8, 2, 500)
		with patch.object(controller.frappe, "msgprint"):
			correction = frappe.get_doc(DOCTYPE, filed.make_correction())
		self.addCleanup(discard, correction.name)
		self.assertEqual(
			[(row.vat_id, row.reported, row.filed_amount, row.in_file) for row in correction.lines],
			[(AUSTRIAN, 8500, 8000, 1)],
		)
		fake = FakeEric()
		transmission, _, _ = self.transmitted(correction, "send", fake, self.stash(correction))
		self.assertIn('<zm-zeilen waehrung="1" meldeart="11">', fake.runs[0]["nutzdaten"])
		self.assertIn("<betrag>8500</betrag>", fake.runs[0]["nutzdaten"])
		filed.reload()
		self.assertEqual(
			(correction.docstatus, correction.status, correction.filed_via, correction.transferticket),
			(1, "Abgegeben", "eric", TICKET),
		)
		self.assertEqual(filed.status, "Ersetzt")
		self.assertEqual(transmission.status, "Erfolgreich")

	def test_a_berichtigung_that_changes_nothing_sends_nothing(self):
		self.use_runtime()
		filed = self.calculated(7)
		self.transmitted(filed, "send", FakeEric(), self.stash(filed))
		with patch.object(controller.frappe, "msgprint"):
			correction = frappe.get_doc(DOCTYPE, filed.make_correction())
		self.addCleanup(discard, correction.name)
		fake = FakeEric()
		transmission, _, _ = self.transmitted(correction, "validate", fake)
		self.assertEqual((transmission.status, fake.runs), ("Fehlgeschlagen", []))
		self.assertIn("changes nothing that was filed", transmission.messages[-1].text)

	def test_a_statement_elster_accepted_while_its_submission_failed_is_submitted_with_buchen(self):
		self.use_runtime()
		doc = self.calculated(7)
		with patch.object(
			RecapitulativeStatement, "before_submit", side_effect=frappe.ValidationError("Kaputt")
		):
			transmission, _, _ = self.transmitted(doc, "send", FakeEric(), self.stash(doc))
		self.assertEqual(
			(transmission.status, transmission.transferticket, doc.docstatus), ("Erfolgreich", TICKET, 0)
		)
		self.assertIn("Kaputt", transmission.messages[-1].text)
		doc.run_method("onload")
		self.assertTrue(doc.get_onload("elster")["sent"])
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "transmitted already"),
		):
			doc.transmit("send", self.stash(doc))
		enqueue.assert_not_called()
		for attempt, message in (
			(lambda: doc.mark_filed_outside(filed_via="mein_elster"), "submit it with Buchen"),
			(doc.calculate, "as it was sent"),
			(doc.confirm_vat_ids, "as it was sent"),
			(doc.make_csv_file, f"transmitted already with Transferticket {TICKET}"),
		):
			with self.subTest(message=message), self.assertRaisesRegex(frappe.ValidationError, message):
				attempt()
			doc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "as it was sent"):
			doc.discard()
		# Frappe keeps the action of a refused discard on the document; the next request loads it anew.
		doc = frappe.get_doc(DOCTYPE, doc.name)
		doc.lines[0].update({"override": 1, "override_reason": "Nachträglich berichtigt"})
		with self.assertRaisesRegex(frappe.ValidationError, "as it was sent"):
			doc.save()
		doc.reload()
		doc.remarks = "Nachträglich"
		doc.save()
		doc.reload()
		doc.lines[0].override = 1
		with self.assertRaisesRegex(frappe.ValidationError, "as it was sent"):
			doc.submit()
		doc.reload()
		doc.submit()
		self.assertEqual(
			(doc.docstatus, doc.status, doc.filed_via, doc.transferticket, doc.remarks),
			(1, "Abgegeben", "eric", TICKET, "Nachträglich"),
		)

	def test_a_statement_whose_send_has_an_unknown_outcome_keeps_all_but_its_remarks(self):
		"""The BZSt may have the statement as it was sent: until Mein ELSTER shows whether it arrived, a save changes
		nothing but the remarks, nothing rewrites its lines or makes its file, and noting the filing submits it."""
		self.use_runtime()
		doc = self.calculated(9)
		fake = FakeEric(outcome=Outcome.UNKNOWN, messages=(LOST, UNKNOWN_MESSAGE))
		transmission, _, _ = self.transmitted(doc, "send", fake, self.stash(doc))
		refused = f"Whether {transmission.name} reached ELSTER is unknown"
		for attempt in (doc.calculate, doc.confirm_vat_ids, doc.make_csv_file):
			with (
				self.subTest(attempt=attempt.__name__),
				self.assertRaisesRegex(frappe.ValidationError, refused),
			):
				attempt()
			doc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, refused):
			doc.discard()
		# Frappe keeps the action of a refused discard on the document; the next request loads it anew.
		doc = frappe.get_doc(DOCTYPE, doc.name)
		for change in (
			lambda: doc.lines[0].update({"override": 1, "override_reason": "Nachträglich berichtigt"}),
			lambda: doc.update({"anzeige": 1, "remarks": "Mit Anzeige"}),
			lambda: doc.update({"filed_via": "mein_elster", "transferticket": MEIN_ELSTER_TICKET}),
		):
			change()
			with self.assertRaisesRegex(frappe.ValidationError, refused):
				doc.save()
			doc.reload()
		doc.remarks = "In Mein ELSTER nachgesehen"
		doc.save()
		doc.mark_filed_outside(filed_via="mein_elster", transferticket=MEIN_ELSTER_TICKET)
		doc.reload()
		self.assertEqual(
			(doc.docstatus, doc.status, doc.filed_via, doc.transferticket, doc.remarks),
			(1, "Abgegeben", "mein_elster", MEIN_ELSTER_TICKET, "In Mein ELSTER nachgesehen"),
		)

	def test_one_transmission_at_a_time(self):
		doc = self.calculated(10)
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
		for attempt in (
			doc.calculate,
			doc.confirm_vat_ids,
			lambda: doc.mark_filed_outside(filed_via="mein_elster"),
		):
			doc.reload()
			with (
				patch("frappe.enqueue") as enqueue,
				self.assertRaisesRegex(frappe.ValidationError, "running"),
			):
				attempt()
			enqueue.assert_not_called()

	def test_the_form_releases_a_lock_whose_job_is_gone(self):
		self.use_runtime()
		doc = self.calculated(10)
		name, job = self.transmit(doc, "send", self.stash(doc))
		doc.reload()
		with patch(IS_JOB_ENQUEUED, return_value=False):
			doc.run_method("onload")
			self.assertTrue(doc.get_onload("elster")["stale"])
			doc.release_stale_transmission()
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "transmission_in_progress"), 0)
		stale = frappe.get_doc(TRANSMISSION, name)
		self.assertEqual((stale.status, stale.outcome), ("Unbekannt", "unknown"))
		fake = FakeEric()
		self.run_job(job, fake)
		self.assertEqual(fake.runs, [])

	def test_filing_outside_steuerbote_is_recorded_as_an_elster_transmission(self):
		doc = self.calculated(10)
		name = doc.mark_filed_outside(
			filed_via="mein_elster", transferticket=MEIN_ELSTER_TICKET, filed_on="2026-11-02"
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
				date(2026, 11, 2),
			),
		)
		doc.reload()
		self.assertEqual(
			(doc.docstatus, doc.status, doc.filed_via, doc.transferticket),
			(1, "Abgegeben", "mein_elster", MEIN_ELSTER_TICKET),
		)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(TRANSMISSION, name)

	def test_the_form_learns_whether_eric_is_simulated_and_what_the_latest_run_found(self):
		"""As on the VAT Return: hints never stop a check (ERiC-Entwicklerhandbuch 44.3.6.0, Kap. 5.1.2.4.1)."""
		doc = self.calculated(10)
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
		self.assertIsNone(doc.get_onload("elster_run"))
		hint = Message("17004518", "Die USt-IdNr. ist unschlüssig.", HINT)
		transmission, _, _ = self.transmitted(doc, "validate", FakeEric(messages=(hint,)))
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
		self.assertEqual(
			{key: doc.get_onload("elster_run")[key] for key in ("name", "status", "errors", "hints")},
			{"name": transmission.name, "status": "Erfolgreich", "errors": 0, "hints": 1},
		)

	def test_the_statement_lists_its_transmissions_and_confirmations_under_its_connections(self):
		doc = self.calculated(10)
		self.transmitted(doc, "validate")
		self.transmitted(doc, "test_send")
		data = frappe.get_meta(DOCTYPE).get_dashboard_data()
		self.assertEqual(
			(data.fieldname, data.dynamic_links, data.non_standard_fieldnames),
			(
				"document",
				{"document": [DOCTYPE, "document_type"]},
				{"VAT ID Confirmation": "recapitulative_statement"},
			),
		)
		self.assertEqual(
			[group["items"] for group in data.transactions], [[TRANSMISSION], ["VAT ID Confirmation"]]
		)
		(links,) = (
			links
			for links in get_open_count(DOCTYPE, doc.name)["count"]["external_links_found"]
			if links["doctype"] == TRANSMISSION
		)
		self.assertEqual(links["count"], 2)

	def test_the_form_brings_the_buttons_and_the_dialog_the_transmissions_share(self):
		script = get_form_meta(DOCTYPE, cached=False).get("__js")
		self.assertIn("function ask_for_certificate(frm, operation, title, texts) {", script)
		self.assertIn("add_transmission_buttons(frm, group, statement_texts());", script)
		self.assertIn("show_latest_run(frm);", script)
		self.assertNotIn("{% include", script)

	def test_the_nutzdaten_name_the_teilnehmernummer_of_the_settings(self):
		self.setting(teilnehmernummer="0300000")
		doc = self.calculated(11)
		_, _, run = self.transmitted(doc, "validate")
		self.assertIn("<zulnr2>0300000</zulnr2>", run.call_args.args[1])

	def test_settings_the_zm_does_not_take_end_in_a_failed_transmission(self):
		doc = self.calculated(11)
		for values, message in (
			({"street": None}, "The street of the Unternehmer is missing."),
			({"phone": "089 #1"}, "The phone number 089 #1 may hold digits"),
			({"ust_idnr": None}, f"Enter the USt-IdNr. of {COMPANY} in the VAT Return Settings"),
		):
			with self.subTest(message=message):
				before = frappe.db.get_value(SETTINGS, COMPANY, list(values), as_dict=True)
				frappe.db.set_value(SETTINGS, COMPANY, values)
				try:
					transmission, _, run = self.transmitted(doc, "validate")
				finally:
					frappe.db.set_value(SETTINGS, COMPANY, dict(before))
				self.assertEqual((transmission.status, run.call_count), ("Fehlgeschlagen", 0))
				self.assertIn(message, transmission.messages[-1].text)
