"""The guards of the app on a site (steuerbote/steuerbote/guards.py): no request writes a record of what Steuerbote did,
whatever its role, what a filing is for stays as it was created, a method the desk calls acts only on a document the
user may reach as it is stored, and only who may submit a document sends its data off the site.

Two invented companies; a manager restricted to the first by a User Permission on Company, and a bookkeeper with the
role Accounts User."""

import json
from unittest.mock import patch

import frappe
import frappe.client
from frappe.core.doctype.deleted_document.deleted_document import restore
from frappe.handler import run_doc_method
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request

from steuerbote.steuerbote.doctype.elster_transmission.transmission import filings
from steuerbote.tests.helpers import make_company, make_mapping, make_settings, make_user
from steuerbote.tests.transmitting import TRANSMISSION, Transmitting

FIRST = "Steuerbote Test Waechter Erste GmbH"
SECOND = "Steuerbote Test Waechter Zweite GmbH"
DATENLIEFERANT_ADDRESS = {"street": "Musterweg 3", "postal_code": "80331", "city": "München"}
MANAGER_OF_THE_FIRST = "steuerbote-waechter-leitung@example.com"
BOOKKEEPER = "steuerbote-waechter-buchhaltung@example.com"
MANAGER = "steuerbote-waechter-manager@example.com"


class GuardsTestCase(Transmitting, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for company, abbr in ((FIRST, "STWE"), (SECOND, "STWZ")):
			make_company(company, abbr)
			make_settings(company, [(2026, "monthly", 1)], filer_name=company, **DATENLIEFERANT_ADDRESS)
			make_mapping(company)
		make_user(MANAGER_OF_THE_FIRST, "Accounts Manager")
		make_user(BOOKKEEPER, "Accounts User")
		make_user(MANAGER, "Accounts Manager")
		if not frappe.db.exists("User Permission", {"user": MANAGER_OF_THE_FIRST, "allow": "Company"}):
			frappe.get_doc(
				{
					"doctype": "User Permission",
					"user": MANAGER_OF_THE_FIRST,
					"allow": "Company",
					"for_value": FIRST,
					"apply_to_all_doctypes": 1,
				}
			).insert(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		self.addCleanup(setattr, frappe.local, "form_dict", frappe.local.form_dict)
		self.addCleanup(setattr, frappe.local, "response", frappe.local.response)

	def draft(self, company: str, period: int, **fields):
		return frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": company,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": period,
				**fields,
			}
		).insert()

	def calculated(self, company: str, period: int):
		doc = self.draft(company, period)
		doc.calculate()
		doc.reload()
		return doc

	def requested(self, method: str, doc: dict) -> None:
		"""What the desk sends when a form calls a method of its document: the document as the client holds it."""
		set_request(method="POST", path="/api/method/run_doc_method")
		frappe.local.response = frappe._dict({"docs": []})
		run_doc_method(method=method, docs=json.dumps(doc, default=str))


class TestRecords(GuardsTestCase):
	"""An ELSTER Transmission, a VAT ID Confirmation and a Deadline Reminder come from Steuerbote alone."""

	def forged(self, draft) -> dict:
		return {
			"doctype": TRANSMISSION,
			"document_type": "VAT Return",
			"document": draft.name,
			"company": draft.company,
			"operation": "send",
			"status": "Erfolgreich",
			"simulated": 0,
		}

	def test_no_way_of_a_request_inserts_a_transmission_that_would_file_a_return(self):
		"""The Administrator inserted a Senden that ELSTER accepted: it locked the return and filed its period."""
		draft = self.draft(SECOND, 9)
		forged = self.forged(draft)
		ways = {
			"insert": lambda: frappe.get_doc(dict(forged)).insert(),
			"insert ignoring permissions": lambda: frappe.get_doc(dict(forged)).insert(
				ignore_permissions=True
			),
			"frappe.client.insert": lambda: frappe.client.insert(dict(forged)),
			"frappe.client.insert_many": lambda: frappe.client.insert_many([dict(forged)]),
		}
		for way, insert in ways.items():
			with self.subTest(way=way), self.assertRaises(frappe.PermissionError):
				insert()
		with patch.dict(frappe.local.flags, {"in_import": True}), self.assertRaises(frappe.PermissionError):
			frappe.get_doc(dict(forged)).insert()
		self.assertEqual(filings("VAT Return", [draft.name]), [])
		self.assertFalse(frappe.db.exists(TRANSMISSION, {"document": draft.name}))

	def test_steuerbote_records_its_own_runs_and_nobody_copies_or_restores_one(self):
		draft = self.calculated(SECOND, 8)
		record = draft.new_transmission("validate", simulated=True, status="Fehlgeschlagen")
		self.assertEqual(frappe.db.get_value(TRANSMISSION, record.name, "document"), draft.name)
		with self.assertRaises(frappe.PermissionError):
			frappe.copy_doc(record).insert(ignore_permissions=True)
		record.remarks = "geändert"
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be changed"):
			record.save(ignore_permissions=True)
		frappe.delete_doc(TRANSMISSION, record.name)
		deleted = frappe.db.get_value(
			"Deleted Document", {"deleted_doctype": TRANSMISSION, "deleted_name": record.name}
		)
		with self.assertRaises(frappe.PermissionError):
			restore(deleted)
		self.assertFalse(frappe.db.exists(TRANSMISSION, record.name))

	def test_no_request_inserts_a_confirmation_or_a_reminder(self):
		confirmation = {
			"doctype": "VAT ID Confirmation",
			"company": FIRST,
			"requested": "ATU12345678",
			"requester": "DE123456789",
			"service": "bzst",
			"outcome": "valid",
			"result": "valid",
		}
		reminder = {
			"doctype": "Deadline Reminder",
			"company": FIRST,
			"kind": "Umsatzsteuer-Voranmeldung",
			"period_label": "Oktober 2026",
			"due_date": "2026-11-10",
			"sent_on": "2026-11-03",
		}
		for record in (confirmation, reminder):
			with self.subTest(doctype=record["doctype"]), self.assertRaises(frappe.PermissionError):
				frappe.client.insert(dict(record))

	def test_a_record_and_a_filing_keep_their_names(self):
		draft = self.calculated(SECOND, 7)
		record = draft.new_transmission("validate", simulated=True, status="Fehlgeschlagen")
		for doctype, name in ((TRANSMISSION, record.name), ("VAT Return", draft.name)):
			for merge in (False, True):
				with self.subTest(doctype=doctype, merge=merge), self.assertRaises(frappe.PermissionError):
					frappe.rename_doc(doctype, name, f"{name}-NEU", force=True, merge=merge)
			self.assertTrue(frappe.db.exists(doctype, name))


class TestIdentity(GuardsTestCase):
	"""A filing keeps the company and the period it was created for, by any way of saving."""

	def test_a_return_keeps_its_company_and_its_period(self):
		draft = self.calculated(FIRST, 6)
		for field, value in (
			("company", SECOND),
			("year", 2027),
			("rhythm", "quarterly"),
			("period_index", 5),
		):
			with self.subTest(field=field):
				doc = frappe.get_doc("VAT Return", draft.name)
				doc.set(field, value)
				with self.assertRaises(frappe.CannotChangeConstantError):
					doc.save()
				with self.assertRaises(frappe.CannotChangeConstantError):
					frappe.client.save({**frappe.get_doc("VAT Return", draft.name).as_dict(), field: value})
				with self.assertRaises(frappe.CannotChangeConstantError):
					frappe.client.set_value("VAT Return", draft.name, field, str(value))
		stored = frappe.get_doc("VAT Return", draft.name)
		self.assertEqual(
			(stored.company, stored.year, stored.rhythm, stored.period_index, stored.status),
			(FIRST, 2026, "monthly", 6, draft.status),
		)

	def test_the_remarks_of_a_return_still_change(self):
		draft = self.calculated(FIRST, 5)
		frappe.client.set_value("VAT Return", draft.name, "remarks", "Von der Steuerberatung geprüft")
		self.assertEqual(
			frappe.db.get_value("VAT Return", draft.name, "remarks"), "Von der Steuerberatung geprüft"
		)


class TestStoredDocument(GuardsTestCase):
	"""A user restricted to the first company reaches nothing of the second through a copy the client sends."""

	def test_a_copy_of_the_mapping_of_another_company_exports_nothing(self):
		stored = frappe.get_doc("VAT Return Mapping", SECOND).as_dict()
		copies = {
			"saved": {**stored, "company": FIRST},
			"unsaved": {**stored, "company": FIRST, "__islocal": 1},
		}
		with self.set_user(MANAGER_OF_THE_FIRST):
			for kind, copy in copies.items():
				with (
					self.subTest(copy=kind),
					self.assertRaises((frappe.PermissionError, frappe.ValidationError)),
				):
					self.requested("export_mapping", copy)
			own = frappe.get_doc("VAT Return Mapping", FIRST).as_dict()
			self.requested("export_mapping", own)
		self.assertTrue(frappe.response["message"]["file_url"])

	def test_a_copy_of_the_return_of_another_company_starts_nothing(self):
		draft = self.calculated(SECOND, 4)
		copy = {**draft.as_dict(), "company": FIRST}
		with self.set_user(MANAGER_OF_THE_FIRST):
			for method in ("release_stale_transmission", "release_stale_confirmation", "make_import_file"):
				with self.subTest(method=method), self.assertRaises(frappe.PermissionError):
					self.requested(method, copy)


class TestSending(GuardsTestCase):
	"""Testsenden and the confirmation of USt-IdNrn. send data off the site and need the permission to submit."""

	def test_a_bookkeeper_checks_a_return_but_sends_nothing(self):
		draft = self.calculated(FIRST, 3)
		with self.set_user(BOOKKEEPER), patch("frappe.enqueue") as enqueue:
			for start in (lambda: draft.transmit("test_send"), draft.confirm_vat_ids):
				with self.assertRaises(frappe.PermissionError):
					start()
			draft.transmit("validate")
		self.assertEqual(enqueue.call_count, 1)
		self.assertEqual(enqueue.call_args.kwargs["operation"], "validate")

	def test_a_manager_test_sends_a_return(self):
		draft = self.calculated(FIRST, 2)
		with self.set_user(MANAGER), patch("frappe.enqueue") as enqueue:
			draft.transmit("test_send")
		self.assertEqual(enqueue.call_args.kwargs["operation"], "test_send")
