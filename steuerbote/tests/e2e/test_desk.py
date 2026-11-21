"""The way in: the login of the Administrator, the entry Steuern on the rail of ERPNext and the workspace Steuern
with its shortcuts and its number card.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import re

from steuerbote.tests.e2e import data


def test_the_administrator_logs_in_and_opens_steuern_from_the_rail_of_erpnext(
	visitor, expect, admin_password
):
	page = visitor.page
	visitor.open("/login")
	page.locator("#login_email").fill("Administrator")
	page.locator("#login_password").fill(admin_password)
	page.locator("#login_password").press("Enter")
	expect(page).to_have_url(re.compile(r"/desk$"))
	visitor.open_steuern_from_the_rail()
	expect(page).to_have_url(re.compile(f"{re.escape(data.WORKSPACE_ROUTE)}$"))
	shortcuts = page.locator(".shortcut-widget-box")
	expect(shortcuts).to_have_count(len(data.SHORTCUTS))
	expect(shortcuts).to_contain_text(list(data.SHORTCUTS))
	expect(page.locator(".number-widget-box")).to_contain_text("Offene Voranmeldungen")


def test_a_shortcut_of_the_workspace_opens_its_list(desk, expect):
	desk.open(data.WORKSPACE_ROUTE)
	desk.page.locator('.shortcut-widget-box[aria-label="Voranmeldungen"]').click()
	expect(desk.page).to_have_url(re.compile(r"/desk/steuerbote/vat-return(/view/list)?$"))
	expect(desk.list_rows().filter(has_text=data.COMPANY)).to_have_count(2)
