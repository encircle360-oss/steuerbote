import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.tests.helpers import make_company

# What went to the tax authorities and the proof of the confirmations of USt-IdNrn.
FILINGS = frozenset(
	{
		"VAT ID Confirmation",
		"Recapitulative Statement",
		"VAT Return Extension",
		"VAT Return",
		"ELSTER Transmission",
	}
)


class InstallationTest(IntegrationTestCase):
	def test_app_is_installed(self):
		self.assertIn("steuerbote", frappe.get_installed_apps())

	def test_erpnext_is_installed_as_required(self):
		self.assertIn("erpnext", frappe.get_installed_apps())

	def test_module_is_registered(self):
		self.assertTrue(frappe.db.exists("Module Def", "Steuerbote"))

	def test_deleting_the_transactions_of_a_company_leaves_its_filings_out(self):
		"""ERPNext's Delete Company Transactions deletes the documents of each DocType linked to the company with
		frappe.db.delete, past on_trash, unless the DocType is excluded; the hook company_data_to_be_ignored
		excludes the filings by default."""
		company = make_company("Steuerbote Test Transaktionen löschen GmbH", "STTL")
		record = frappe.get_doc({"doctype": "Transaction Deletion Record", "company": company}).insert()
		record.generate_to_delete_list()
		excluded = {row.doctype_name for row in record.doctypes_to_be_ignored}
		deleted = {row.doctype_name for row in record.doctypes_to_delete}
		self.assertIn("Sales Invoice", deleted)
		self.assertEqual(FILINGS - excluded, set())
		self.assertEqual(FILINGS & deleted, set())
