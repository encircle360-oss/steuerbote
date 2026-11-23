"""The way in: the login of the Administrator, the entry Steuern on the rail of ERPNext, the workspace Steuern with
its sections, shortcuts and number card, and the sidebar Steuerbote with its groups and icons. The tests of the
sidebar and the workspace leave a screenshot of each under --output.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import re

from steuerbote.tests.e2e import data

# Tall enough for the sidebar with every group open and for the whole workspace.
SCREENSHOT_VIEWPORT = {"width": 1440, "height": 1600}


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


def test_the_sidebar_shows_every_group_and_entry_with_its_icon(desk, screenshots):
	"""Every entry beside the groups and every group draws a symbol the page holds; the entries of a group follow
	it without an icon, as in the sidebars of ERPNext."""
	desk.page.set_viewport_size(SCREENSHOT_VIEWPORT)
	desk.open(data.WORKSPACE_ROUTE)
	desk.open_sidebar_groups()
	entries = desk.sidebar()
	assert {
		entry["label"]: tuple(child["label"] for child in entry["group"]) for entry in entries
	} == data.SIDEBAR
	assert [entry["label"] for entry in entries] == list(data.SIDEBAR)
	assert [(entry["label"], entry["symbol"]) for entry in entries if not entry["drawn"]] == []
	assert [child["label"] for entry in entries for child in entry["group"] if child["icon"]] == []
	desk.page.locator(".body-sidebar").screenshot(path=screenshots / "sidebar.png")


def test_an_entry_of_a_group_opens_its_list(desk, expect):
	desk.open(data.WORKSPACE_ROUTE)
	desk.open_sidebar_groups()
	desk.page.locator(".body-sidebar").get_by_role("link", name="USt-Erklärungen", exact=True).click()
	expect(desk.page).to_have_url(re.compile(r"/desk/steuerbote/annual-vat-return(/view/list)?$"))
	expect(desk.list_rows().filter(has_text=data.COMPANY)).to_have_count(1)


def test_the_workspace_shows_its_sections_with_the_jahresmeldungen(desk, screenshots):
	desk.page.set_viewport_size(SCREENSHOT_VIEWPORT)
	desk.open(data.WORKSPACE_ROUTE)
	sections = desk.workspace_sections()
	assert [header for header, _shortcuts in sections] == list(data.WORKSPACE_SECTIONS)
	assert {header: tuple(shortcuts) for header, shortcuts in sections} == data.WORKSPACE_SECTIONS
	desk.page.screenshot(path=screenshots / "workspace.png", full_page=True)
