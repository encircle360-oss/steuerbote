"""ERPNext's Delete Company Transactions keeps the Annual Filing Settings and the annual documents of a company."""

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.tests.helpers import make_company

# The annual documents of stage 3; each counts once its module brings its DocType.
ANNUAL_DOCUMENTS = (
	"Annual VAT Return",
	"Electronic Balance Sheet",
	"Corporate Income Tax Return",
	"Trade Tax Return",
	"Annual Accounts",
)


class TransactionDeletionTest(IntegrationTestCase):
	def test_deleting_the_transactions_of_a_company_keeps_its_annual_filing_settings_and_annual_documents(
		self,
	):
		"""The record lists the DocTypes it leaves alone from the hook company_data_to_be_ignored, and refuses to save
		with a name there that is no DocType."""
		company = make_company("Steuerbote Test Jahresmeldungen löschen GmbH", "STJL")
		record = frappe.get_doc({"doctype": "Transaction Deletion Record", "company": company}).insert()
		record.generate_to_delete_list()
		excluded = {row.doctype_name for row in record.doctypes_to_be_ignored}
		deleted = {row.doctype_name for row in record.doctypes_to_delete}
		kept = {
			"Annual Filing Settings",
			*(name for name in ANNUAL_DOCUMENTS if frappe.db.exists("DocType", name)),
		}
		self.assertEqual(kept - excluded, set())
		self.assertEqual(kept & deleted, set())
