"""A VAT ID Confirmation keeps each query of a confirmation with its answer, and nobody changes or deletes it."""

from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.steuerbote.doctype.vat_id_confirmation.vat_id_confirmation import latest, store
from steuerbote.tests.helpers import make_company
from steuerbote.vatid.result import Details
from steuerbote.vatid.service import confirm
from steuerbote.vatid.tests.fakes import DETAILS, REQUESTED, REQUESTER, FakeClock, FakeFetch, bzst

# The company is made by the test itself.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Recapitulative Statement", "User"]

DOCTYPE = "VAT ID Confirmation"
COMPANY = "Steuerbote Test Bestätigung GmbH"
NEIGHBOUR = "Steuerbote Test Bestätigung Nachbar GmbH"


def confirmed(*answers, details=None):
	return confirm(REQUESTED, REQUESTER, details, FakeFetch(*answers), FakeClock())


class TestVATIDConfirmation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STBS")
		make_company(NEIGHBOUR, "STBN")

	def answer_of(self, name: str):
		return frappe.get_doc("File", {"attached_to_doctype": DOCTYPE, "attached_to_name": name})

	def test_keeps_each_query_with_its_answer_the_later_pointing_to_the_earlier(self):
		qualified = bzst("evatr-0000", ergFirmenname="A", ergStrasse="B", ergPlz="A", ergOrt="A")
		last = store(confirmed(bzst("evatr-0000"), qualified, details=DETAILS), COMPANY)
		record = frappe.get_doc(DOCTYPE, last)
		first = frappe.get_doc(DOCTYPE, record.previous)
		self.assertEqual(
			[
				(item.qualified, item.result, item.details_name, item.street_match or None)
				for item in (first, record)
			],
			[(0, "valid", None, None), (1, "valid", DETAILS.name, "B")],
		)
		self.assertEqual(
			(record.company, record.requester, record.user), (COMPANY, REQUESTER, "Administrator")
		)
		answer = self.answer_of(last)
		self.assertEqual((answer.is_private, record.response_file), (1, answer.file_url))
		self.assertEqual(Path(answer.get_full_path()).read_bytes(), qualified.body)

	def test_keeps_an_address_and_an_answer_of_any_length(self):
		"""An address line of ERPNext holds 240 characters, and a service may send a longer status or number than
		the 140 characters of a Data field; the records keep them whole, the simple query with the qualified one."""
		street = "Lange Straße " + "1" * 227
		status = "evatr-" + "9" * 200
		number = "0a1b2c3d" * 25
		details = Details(DETAILS.name, DETAILS.city, DETAILS.postcode, street)
		last = store(confirmed(bzst("evatr-0000"), bzst(status, id=number), details=details), COMPANY)
		record = frappe.get_doc(DOCTYPE, last)
		self.assertEqual(
			(len(street), record.details_street, record.status_code, record.consultation_id),
			(240, street, status, number),
		)
		self.assertEqual(frappe.db.get_value(DOCTYPE, record.previous, "status_code"), "evatr-0000")

	def test_a_query_without_an_answer_keeps_no_file(self):
		name = store(confirmed(OSError("timed out"), OSError("timed out")), COMPANY)
		record = frappe.get_doc(DOCTYPE, name)
		self.assertEqual((record.service, record.result, record.response_file), ("vies", "unknown", None))
		self.assertFalse(frappe.db.exists("File", {"attached_to_doctype": DOCTYPE, "attached_to_name": name}))

	def test_latest_gives_the_newest_record_of_each_number_of_the_company(self):
		store(confirmed(bzst("evatr-2001", 404)), COMPANY)
		newest = store(confirmed(bzst("evatr-0000")), COMPANY)
		store(confirmed(bzst("evatr-2001", 404)), NEIGHBOUR)
		found = latest(COMPANY, [REQUESTED, "FR12345678901", ""])
		self.assertEqual(list(found), [REQUESTED])
		self.assertEqual((found[REQUESTED].name, found[REQUESTED].result), (newest, "valid"))
		self.assertEqual(latest(COMPANY, []), {})

	def test_nobody_changes_or_deletes_a_record_or_its_answer(self):
		name = store(confirmed(bzst("evatr-0000")), COMPANY)
		record = frappe.get_doc(DOCTYPE, name)
		record.message = "Geändert"
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be changed"):
			record.save(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be deleted"):
			frappe.delete_doc(DOCTYPE, name, ignore_permissions=True)
		answer = self.answer_of(name)
		with self.assertRaisesRegex(frappe.ValidationError, "part of the proof"):
			frappe.delete_doc("File", answer.name, ignore_permissions=True)
		answer.reload()
		answer.is_private = 0
		with self.assertRaisesRegex(frappe.ValidationError, "part of the proof"):
			answer.save(ignore_permissions=True)
