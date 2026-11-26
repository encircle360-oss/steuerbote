"""The files of an ELSTER Transmission and the answer of a USt-IdNr.-Bestätigung stay as they were stored.

The job that stores them runs as the user who started it, and that user owns the Files, which Frappe lets the
owner of a File change and delete. So the tests act as that user, through the permission checks of Frappe.
"""

from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.steuerbote.doctype.vat_id_confirmation.vat_id_confirmation import store
from steuerbote.tests.helpers import make_company, make_mapping, make_settings, make_user
from steuerbote.tests.transmitting import TRANSMISSION, Transmitting
from steuerbote.vatid.service import confirm
from steuerbote.vatid.tests.fakes import REQUESTED, REQUESTER, FakeClock, FakeFetch, bzst

COMPANY = "Steuerbote Test Belegdateien GmbH"
CONFIRMATION = "VAT ID Confirmation"
JOB_USER = "steuerbote-belegdateien@example.com"
DATENLIEFERANT_ADDRESS = {
	"filer_name": COMPANY,
	"street": "Hauptstraße 1",
	"postal_code": "80331",
	"city": "München",
}
KEPT = (
	"attached_to_doctype",
	"attached_to_name",
	"attached_to_field",
	"file_name",
	"file_url",
	"is_private",
	"content_hash",
)
CHANGES = {
	"detached": {"attached_to_doctype": None, "attached_to_name": None, "attached_to_field": None},
	"attached to another record": {"attached_to_name": "ELSTER-2026-99999"},
	"put into another field": {"attached_to_field": "response_xml"},
	"made public": {"is_private": 0},
	"renamed": {"file_name": "umbenannt.pdf"},
	"pointed to another file": {"file_url": "/private/files/anderswo.pdf"},
}


class TestRecordFiles(Transmitting, IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STBD")
		make_settings(COMPANY, [(2026, "monthly", 1)], **DATENLIEFERANT_ADDRESS)
		make_mapping(COMPANY)
		make_user(JOB_USER, "Accounts Manager")

	def transmission_files(self, period: int):
		"""A simulated Testsenden the job user ran, with the Nutzdaten and the protocol it stored."""
		with self.set_user(JOB_USER):
			doc = frappe.get_doc(
				{
					"doctype": "VAT Return",
					"company": COMPANY,
					"year": 2026,
					"rhythm": "monthly",
					"period_index": period,
				}
			).insert()
			doc.calculate()
			doc.reload()
			transmission, _, _ = self.transmitted(doc, "test_send")
		files = [self.attachment(transmission, fieldname) for fieldname in ("xml", "protocol_pdf")]
		self.assertEqual({file.owner for file in files}, {JOB_USER})
		return transmission, files

	def answer_of_a_confirmation(self):
		"""The answer the BZSt gave to a query of the job user, kept with its USt-IdNr.-Bestätigung."""
		with self.set_user(JOB_USER):
			name = store(
				confirm(REQUESTED, REQUESTER, None, FakeFetch(bzst("evatr-0000")), FakeClock()), COMPANY
			)
		answer = frappe.get_doc("File", {"attached_to_doctype": CONFIRMATION, "attached_to_name": name})
		self.assertEqual(answer.owner, JOB_USER)
		return answer

	def assertKept(self, file, message: str) -> None:
		"""The owner of the File can neither change, rename nor delete it, and it stays as it was stored."""
		stored = frappe.db.get_value("File", file.name, KEPT, as_dict=True)
		with self.set_user(file.owner):
			for case, values in CHANGES.items():
				changed = frappe.get_doc("File", file.name)
				changed.update(values)
				with self.subTest(case=case), self.assertRaisesRegex(frappe.ValidationError, message):
					changed.save()
			with self.subTest(case="deleted"), self.assertRaisesRegex(frappe.ValidationError, message):
				frappe.delete_doc("File", file.name)
		with (
			self.subTest(case="renamed as a record"),
			self.assertRaisesRegex(frappe.ValidationError, message),
		):
			frappe.rename_doc("File", file.name, f"{file.name}-umbenannt", force=True)
		self.assertEqual(frappe.db.get_value("File", file.name, KEPT, as_dict=True), stored)
		self.assertTrue(Path(frappe.get_doc("File", file.name).get_full_path()).is_file())

	def test_the_files_of_a_transmission_stay_as_its_run_stored_them(self):
		transmission, files = self.transmission_files(1)
		for file in files:
			with self.subTest(file=file.attached_to_field):
				self.assertKept(
					file, f"ELSTER Transmission {transmission.name} and stays as the run stored it"
				)

	def test_the_answer_of_a_confirmation_stays_part_of_the_proof(self):
		answer = self.answer_of_a_confirmation()
		self.assertKept(answer, f"The answer of {answer.attached_to_name} is part of the proof")

	def test_the_cross_of_the_form_cannot_remove_the_answer_of_a_confirmation(self):
		"""The form of a confirmation shows the × of its attachment to the Administrator, who holds every permission
		(R3-F-13); the server refuses what it calls, remove_attach, and the answer stays with its record."""
		from frappe.desk.form.utils import remove_attach

		answer = self.answer_of_a_confirmation()
		frappe.form_dict.update({"fid": answer.name, "dt": CONFIRMATION, "dn": answer.attached_to_name})
		self.addCleanup(frappe.form_dict.clear)
		with self.assertRaisesRegex(frappe.ValidationError, "is part of the proof"):
			remove_attach()
		self.assertTrue(frappe.db.exists("File", answer.name))

	def test_deleting_a_transmission_deletes_its_files(self):
		transmission, files = self.transmission_files(2)
		frappe.delete_doc(TRANSMISSION, transmission.name)
		self.assertEqual([frappe.db.exists("File", file.name) for file in files], [None, None])

	def test_a_file_with_the_same_content_cannot_make_the_file_of_a_record_public(self):
		"""Frappe stores equal content once: a File of its own with the content of the protocol shares its file on
		disk, and making that File public would move the file and rewrite every File that shares it."""
		_, files = self.transmission_files(3)
		protocol = files[1]
		with self.set_user(JOB_USER):
			copy = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "kopie.pdf",
					"is_private": 1,
					"content": protocol.get_content(),
				}
			).insert()
			self.assertEqual(copy.file_url, protocol.file_url)
			copy.is_private = 0
			with self.assertRaisesRegex(frappe.ValidationError, "shares its content with a file of"):
				copy.save()
			copy.reload()
			copy.file_name = "kopie-umbenannt.pdf"
			copy.save()
		self.assertEqual(
			frappe.db.get_value("File", protocol.name, ["is_private", "file_url"]), (1, protocol.file_url)
		)
		self.assertTrue(Path(protocol.get_full_path()).is_file())
