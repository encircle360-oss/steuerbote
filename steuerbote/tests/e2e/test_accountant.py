"""The desk of a user with the role Accounts User alone: the entry Steuern on the rail and the workspace work for
it, and what only a System Manager may open stays hidden.

The page Steuerbote einrichten is for a System Manager or an Accounts Manager, so its shortcut stays hidden.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import re

from steuerbote.tests.e2e import data

# The ERiC Settings are the only page of the sidebar Steuerbote for the System Manager alone.
SYSTEM_MANAGER_ONLY = "ERiC-Einstellungen"
SIDEBAR = (
	"Steuern",
	"Voranmeldungen",
	"Zusammenf. Meldungen",
	"USt-Erklärungen",
	"Einstellungen",
	"UStVA Kennzahlen",
)


def test_an_accountant_opens_steuern_from_the_rail_of_erpnext(accountant, expect):
	accountant.open("/desk")
	accountant.open_steuern_from_the_rail()
	page = accountant.page
	expect(page).to_have_url(re.compile(f"{re.escape(data.WORKSPACE_ROUTE)}$"))
	expect(page.locator(".shortcut-widget-box")).to_have_count(len(data.SHORTCUTS) - 1)
	expect(page.locator(f'.shortcut-widget-box[aria-label="{data.SETUP_SHORTCUT}"]')).to_have_count(0)
	accountant.open_sidebar_groups()
	sidebar = page.locator(".body-sidebar")
	for label in SIDEBAR:
		expect(sidebar.get_by_text(label, exact=True)).to_be_visible()
	expect(sidebar.get_by_text(SYSTEM_MANAGER_ONLY, exact=True)).to_have_count(0)


def test_an_accountant_calculates_the_vat_return(accountant, expect, records):
	accountant.open(f"/desk/vat-return/{records['vat_return']}")
	accountant.calculate()
	expect(accountant.field("status")).to_contain_text("Bereit")


def test_the_eric_settings_stay_closed_to_an_accountant(accountant, expect):
	accountant.open("/desk/eric-settings")
	expect(accountant.dialog()).to_contain_text(data.ACCOUNTANT)
	expect(accountant.field("hersteller_id")).to_have_count(0)
