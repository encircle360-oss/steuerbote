import frappe
from frappe.tests import IntegrationTestCase


class InstallationTest(IntegrationTestCase):
	def test_app_is_installed(self):
		self.assertIn("steuerbote", frappe.get_installed_apps())

	def test_erpnext_is_installed_as_required(self):
		self.assertIn("erpnext", frappe.get_installed_apps())

	def test_module_is_registered(self):
		self.assertTrue(frappe.db.exists("Module Def", "Steuerbote"))
