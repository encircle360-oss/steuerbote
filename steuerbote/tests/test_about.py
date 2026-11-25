import frappe
from frappe.desk.desktop import get_desktop_page
from frappe.tests import IntegrationTestCase
from frappe.utils.change_log import get_versions

from steuerbote.steuerbote import about, about_block
from steuerbote.tests.helpers import make_user

ACCOUNTS_USER = "steuerbote-about@example.com"


class AboutBlockTest(IntegrationTestCase):
	def installed_version(self) -> str:
		return get_versions()["steuerbote"]["version"]

	def test_the_endpoint_shows_the_installed_version_and_the_links(self):
		markup = about_block.render()
		self.assertIn(f"Steuerbote {self.installed_version()}", markup)
		for url in (
			about.REPOSITORY,
			f"{about.REPOSITORY}/tree/main/docs",
			f"{about.REPOSITORY}/issues",
			f"{about.REPOSITORY}/blob/main/docs/haftungsausschluss.md",
			"https://encircle360.com/?ref=steuerbote",
		):
			with self.subTest(url=url):
				self.assertIn(f'href="{url}"', markup)

	def test_the_endpoint_speaks_the_language_of_the_user(self):
		frappe.local.lang = "de"
		try:
			self.assertIn("Steuerbote ersetzt keine steuerliche Beratung.", about_block.render())
		finally:
			frappe.local.lang = "en"

	def test_the_block_is_installed_and_open_to_every_user_of_the_desk(self):
		block = frappe.get_doc("Custom HTML Block", about.BLOCK)
		self.assertEqual((block.private, block.roles), (0, []))
		self.assertIn("steuerbote.steuerbote.about_block.render", block.script)
		make_user(ACCOUNTS_USER, "Accounts User")
		self.assertTrue(frappe.has_permission("Custom HTML Block", "read", about.BLOCK, user=ACCOUNTS_USER))

	def test_the_workspace_steuern_shows_the_block(self):
		page = get_desktop_page("Steuern")
		self.assertIn(about.BLOCK, [block.label for block in page["custom_blocks"]["items"]])

	def test_the_line_of_the_printouts_names_the_installed_version(self):
		line = frappe.render_template("{% include 'steuerbote/templates/includes/created_with.html' %}", {})
		self.assertIn(f"Erstellt mit Steuerbote {self.installed_version()}", line)
