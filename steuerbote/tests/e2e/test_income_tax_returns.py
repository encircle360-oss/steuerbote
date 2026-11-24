"""The Körperschaft- and the Gewerbesteuererklärung of the seed's company of the income taxes for 2026: Berechnen, the
lines of the forms, the finding that the forms of the year are provisional and the print preview of each; and a new
Körperschaftsteuererklärung, which opens as a draft of the default company. Nothing goes to ELSTER, so the list of the
ELSTER Transmissions of the first company keeps its one row. Berechnen leaves the picture of the README of each return,
koerperschaftsteuererklaerung.png and gewerbesteuererklaerung.png, under --output.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import json

from steuerbote.tests.e2e import data

CORPORATE = "Corporate Income Tax Return"
TRADE = "Trade Tax Return"
ROUTES = {CORPORATE: "/desk/corporate-income-tax-return", TRADE: "/desk/trade-tax-return"}
TITLES = {CORPORATE: "Körperschaftsteuererklärung", TRADE: "Gewerbesteuererklärung"}
# Anlage GK line 11, the Jahresüberschuss, and Anlage ZVE line 70, the zu versteuerndes Einkommen.
CORPORATE_LINES = ("E8002001", "E8007501")
# GewSt 1 A line 39, the Gewinn.
TRADE_LINES = ("E4001703",)
PROVISIONAL = {CORPORATE: "KST-VORLAEUFIG", TRADE: "GEWST-VORLAEUFIG"}
PROVISIONAL_NOTE = f"vorläufig (Jahresdokumentation {data.DOCUMENTATION_YEAR})"


def seeded(desk, base_url, doctype: str) -> str:
	"""The name of the return of the seed, which its naming series gives it on the site, read as the desk of the test
	reads it."""
	filters = {"company": data.INCOME_TAX_COMPANY, "year": data.YEAR, "docstatus": 0}
	response = desk.page.request.get(
		f"{base_url}/api/resource/{doctype}", params={"filters": json.dumps(filters), "fields": '["name"]'}
	)
	assert response.ok, f"{response.url} answered {response.status}: {response.text()[:2000]}"
	names = [row["name"] for row in response.json()["data"]]
	assert len(names) == 1, f"the seed makes one {doctype} with {filters}, the site has {names}"
	return names[0]


def calculated(desk, expect, base_url, doctype: str) -> str:
	"""Open the return of the seed, Berechnen, and wait for the status it leaves."""
	name = seeded(desk, base_url, doctype)
	desk.open(f"{ROUTES[doctype]}/{name}")
	desk.calculate()
	expect(desk.field("status")).to_contain_text("Berechnet")
	return name


def test_berechnen_computes_the_koerperschaftsteuer_and_holds_it_for_the_provisional_forms(
	desk, expect, base_url, screenshots
):
	calculated(desk, expect, base_url, CORPORATE)
	lines = desk.grid_rows("lines")
	for feldkennung in CORPORATE_LINES:
		expect(lines.filter(has_text=feldkennung)).to_have_count(1)
	expect(desk.grid_cells("findings", "code").filter(has_text=PROVISIONAL[CORPORATE])).to_have_count(1)
	desk.picture(screenshots / "koerperschaftsteuererklaerung.png", "net_income")


def test_berechnen_computes_the_gewerbesteuer_on_the_koerperschaftsteuererklaerung_of_the_year(
	desk, expect, base_url, screenshots
):
	corporate = seeded(desk, base_url, CORPORATE)
	calculated(desk, expect, base_url, TRADE)
	expect(desk.field("corporate_income_tax_return").locator("input")).to_have_value(corporate)
	lines = desk.grid_rows("lines")
	for feldkennung in TRADE_LINES:
		expect(lines.filter(has_text=feldkennung)).to_have_count(1)
	expect(desk.grid_rows("municipalities")).to_have_count(1)
	expect(desk.grid_cells("findings", "code").filter(has_text=PROVISIONAL[TRADE])).to_have_count(1)
	desk.picture(screenshots / "gewerbesteuererklaerung.png", "profit")


def test_the_print_preview_shows_each_return_and_that_its_forms_are_provisional(desk, expect, base_url):
	for doctype in (CORPORATE, TRADE):
		name = seeded(desk, base_url, doctype)
		desk.open(f"/desk/print/{doctype}/{name}")
		preview = desk.page.locator("iframe").filter(visible=True).content_frame.locator("body")
		expect(preview).to_contain_text(f"{TITLES[doctype]} {data.YEAR}")
		expect(preview).to_contain_text(PROVISIONAL_NOTE)
		expect(preview).to_contain_text(data.INCOME_TAX_COMPANY)


def test_a_new_koerperschaftsteuererklaerung_opens_as_a_draft_of_the_default_company(desk, expect):
	desk.open(f"{ROUTES[CORPORATE]}/new")
	expect(desk.field("company").locator("input")).to_have_value(data.COMPANY)
	assert desk.page.evaluate("() => cur_frm.is_new()")
	expect(desk.button("Berechnen")).to_have_count(0)
