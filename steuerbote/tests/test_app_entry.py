"""Where the desk offers Steuerbote, and to whom: the apps screen and the rail beside the areas of ERPNext,
for the roles of the workspace "Steuern"."""

from contextlib import contextmanager

import frappe
from frappe.apps import get_apps, get_route
from frappe.boot import get_app_data, get_app_rail_host_map, get_module_sidebars
from frappe.desk.desktop import get_workspaces
from frappe.tests import IntegrationTestCase

from steuerbote.permissions import APP_ROLES

# The users of the tests are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]

ACCOUNTANT = "steuerbote-desk-buchhaltung@example.com"
SALES = "steuerbote-desk-vertrieb@example.com"
WORKSPACE = "Steuern"
SHELL = "Steuerbote"
APPS_SCREEN_ENTRY = {
	"name": "steuerbote",
	"logo": "/assets/steuerbote/images/steuerbote-logo.svg",
	"title": "Steuerbote",
	"route": "/desk/steuern",
}


def make_user(email: str, role: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Steuerbote",
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	return email


def forget_the_request():
	"""The desk keeps what it works out for the length of a request, and a test runs as one request."""
	if getattr(frappe.local, "request_cache", None):
		frappe.local.request_cache.clear()


class AppEntryTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(ACCOUNTANT, "Accounts User")
		make_user(SALES, "Sales User")

	@contextmanager
	def desk_of(self, user: str):
		with self.set_user(user):
			forget_the_request()
			try:
				yield
			finally:
				forget_the_request()

	def on_the_apps_screen(self) -> dict | None:
		return next((app for app in get_apps() if app["name"] == "steuerbote"), None)

	def test_the_apps_screen_offers_steuerbote_with_its_logo_and_workspace(self):
		with self.desk_of(ACCOUNTANT):
			entry = self.on_the_apps_screen()
		self.assertIsNotNone(entry)
		self.assertEqual({key: entry[key] for key in APPS_SCREEN_ENTRY}, APPS_SCREEN_ENTRY)
		self.assertEqual(get_route("steuerbote"), APPS_SCREEN_ENTRY["route"])

	def test_the_apps_screen_leaves_steuerbote_out_for_other_roles(self):
		with self.desk_of(SALES):
			self.assertIsNone(self.on_the_apps_screen())

	def test_the_app_is_meant_for_the_roles_of_its_workspace(self):
		self.assertEqual({row.role for row in frappe.get_doc("Workspace", WORKSPACE).roles}, APP_ROLES)

	def test_the_workspace_is_visible_for_the_roles_of_the_app_only(self):
		with self.desk_of(ACCOUNTANT):
			self.assertIn(WORKSPACE, {page.name for page in get_workspaces()["pages"]})
		with self.desk_of(SALES):
			self.assertNotIn(WORKSPACE, {page.name for page in get_workspaces()["pages"]})

	def test_the_rail_of_erpnext_leads_to_the_sidebar_of_steuerbote(self):
		self.assertEqual(get_app_rail_host_map().get("steuerbote"), "erpnext")
		with self.desk_of(ACCOUNTANT):
			erpnext = next(app for app in get_app_data() if app["app_name"] == "erpnext")
			sidebars = get_module_sidebars()
		rail = [(row["link_type"], row["link_to"], row["title"]) for row in erpnext["dock"]]
		self.assertIn(("Sidebar", SHELL, WORKSPACE), rail)
		self.assertIn(("Sidebar", "Accounts"), [(link_type, link_to) for link_type, link_to, _ in rail])
		self.assertEqual(sidebars[SHELL]["app"], "steuerbote")

	def test_the_rail_shows_steuern_only_to_who_may_open_the_sidebar(self):
		"""The desk draws a rail entry only for a sidebar in the user's boot, and the boot leaves out a
		sidebar with nothing the user may open."""
		with self.desk_of(SALES):
			self.assertNotIn(SHELL, get_module_sidebars())
