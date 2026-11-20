import frappe
from frappe import _
from frappe.desk.doctype.number_card.number_card import get_result
from frappe.desk.doctype.sidebar.sidebar import resolve_sidebar
from frappe.tests import IntegrationTestCase

from steuerbote.tests.helpers import make_company, make_mapping, make_settings

COMPANY = "Steuerbote Test Arbeitsbereich GmbH"
NUMBER_CARD = "Offene Voranmeldungen"
MODULE = "Steuerbote"
SIDEBAR_LINKS = [
	("Workspace", "Steuern", "Steuern"),
	("DocType", "VAT Return", "VAT Returns"),
	("DocType", "VAT Return Extension", "VAT Return Extensions"),
	("DocType", "Recapitulative Statement", "Recapitulative Statements"),
	("DocType", "VAT ID Confirmation", "VAT ID Confirmations"),
	("DocType", "VAT Return Mapping", "Account Mapping"),
	("DocType", "VAT Return Settings", "Settings"),
	("DocType", "ERiC Settings", "ERiC Settings"),
	("DocType", "ELSTER Transmission", "ELSTER Transmission"),
	("DocType", "Deadline Reminder", "Deadline Reminders"),
	("Report", "UStVA Kennzahlen", "UStVA Kennzahlen"),
	("Report", "Offene Fristen", "Offene Fristen"),
]


class WorkspaceTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STAB")
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)

	def open_returns(self) -> int:
		card = frappe.get_doc("Number Card", NUMBER_CARD)
		return int(get_result(card.as_dict(), card.filters_json))

	def new_return(self, period: int):
		return frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": period,
			}
		).insert()

	def test_the_workspace_steuern_is_installed_with_its_shortcuts_and_number_card(self):
		workspace = frappe.get_doc("Workspace", "Steuern")
		self.assertEqual((workspace.module, workspace.public), ("Steuerbote", 1))
		self.assertEqual(
			sorted((shortcut.type, shortcut.link_to) for shortcut in workspace.shortcuts),
			[
				("DocType", "Recapitulative Statement"),
				("DocType", "Recapitulative Statement"),
				("DocType", "VAT ID Confirmation"),
				("DocType", "VAT Return"),
				("DocType", "VAT Return"),
				("DocType", "VAT Return Extension"),
				("DocType", "VAT Return Mapping"),
				("DocType", "VAT Return Settings"),
				("Report", "Offene Fristen"),
				("Report", "UStVA Kennzahlen"),
			],
		)
		self.assertEqual([card.number_card_name for card in workspace.number_cards], [NUMBER_CARD])

	def test_the_number_card_counts_the_returns_in_draft(self):
		before = self.open_returns()
		first, second = self.new_return(1), self.new_return(2)
		self.assertEqual(self.open_returns(), before + 2)
		first.calculate()
		first.reload()
		first.mark_filed_outside("In Mein ELSTER abgegeben")
		self.assertEqual(self.open_returns(), before + 1)
		second.delete()
		self.assertEqual(self.open_returns(), before)

	def test_the_sidebar_of_the_module_is_installed(self):
		sidebar = frappe.get_doc("Sidebar", MODULE)
		self.assertEqual((sidebar.module, sidebar.app, sidebar.standard), (MODULE, "steuerbote", 1))
		self.assertEqual(
			[(item.link_type, item.link_to, item.label) for item in sidebar.items if item.type == "Link"],
			SIDEBAR_LINKS,
		)

	def test_the_desk_shows_the_sidebar_the_app_ships(self):
		sidebar = resolve_sidebar(MODULE, frappe.session.user)
		self.assertFalse(sidebar.computed)
		self.assertEqual(
			[
				(item["link_type"], item["link_to"], item["label"])
				for item in sidebar.items
				if item["type"] == "Link"
			],
			[(link_type, link_to, _(label)) for link_type, link_to, label in SIDEBAR_LINKS],
		)
