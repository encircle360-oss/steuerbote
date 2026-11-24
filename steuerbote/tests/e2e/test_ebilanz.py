"""The E-Bilanz of the seed's company of the E-Bilanz for 2026: the calculated draft with its positions and the
finding that the site has no HGB-Taxonomie, Berechnen saying how to install it, the print preview with the Bilanz in
Kontoform, the report E-Bilanz Positionen opening a position to its accounts, and a new E-Bilanz, which opens as a
Jahresabschluss of the default company. Nothing goes to ELSTER. The calculated E-Bilanz is the picture of the README,
ebilanz.png, under --output.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import json
from urllib.parse import urlencode

from steuerbote.tests.e2e import data

DOCTYPE = "Electronic Balance Sheet"
ROUTE = "/desk/electronic-balance-sheet"
REPORT = "/desk/query-report/E-Bilanz Positionen"
BANK = "bs.ass.currAss.cashEquiv.bank"
# What the form says when Berechnen finds no taxonomy: the button of the ERiC Settings that installs it.
INSTALL = "Taxonomie einrichten"


def seeded(desk, base_url) -> str:
	"""The name of the E-Bilanz of the seed, which its naming series gives it on the site."""
	filters = {"company": data.EBILANZ_COMPANY, "year": data.YEAR, "docstatus": 0}
	response = desk.page.request.get(
		f"{base_url}/api/resource/{DOCTYPE}", params={"filters": json.dumps(filters), "fields": '["name"]'}
	)
	assert response.ok, f"{response.url} answered {response.status}: {response.text()[:2000]}"
	names = [row["name"] for row in response.json()["data"]]
	assert len(names) == 1, f"the seed makes one {DOCTYPE} with {filters}, the site has {names}"
	return names[0]


def report_row(desk, text: str):
	"""The row of the report's table that shows the text."""
	return desk.page.locator(".dt-scrollable .dt-row").filter(has_text=text)


def test_the_calculated_e_bilanz_shows_its_positions_and_that_the_taxonomy_is_missing(
	desk, expect, base_url, screenshots
):
	desk.open(f"{ROUTE}/{seeded(desk, base_url)}")
	expect(desk.field("status")).to_contain_text("Berechnet")
	expect(desk.grid_cells("findings", "code").filter(has_text="SB-TAXONOMIE")).to_have_count(1)
	expect(desk.grid_rows("positions").filter(has_text=BANK)).to_have_count(1)
	desk.picture(screenshots / "ebilanz.png", "positions")


def test_berechnen_without_the_taxonomy_says_how_to_install_it(desk, expect, base_url):
	desk.open(f"{ROUTE}/{seeded(desk, base_url)}")
	response = desk.run_doc_method("calculate", desk.button("Berechnen").click)
	assert response.status == 417, f"calculate answered {response.status}: {response.text()[:2000]}"
	desk.wait_for_dialog()
	expect(desk.dialog()).to_contain_text(INSTALL)
	desk.close_dialog()
	expect(desk.field("status")).to_contain_text("Berechnet")


def test_the_print_preview_shows_the_bilanz_in_kontoform(desk, expect, base_url):
	desk.open(f"/desk/print/{DOCTYPE}/{seeded(desk, base_url)}")
	preview = desk.page.locator("iframe").filter(visible=True).content_frame.locator("body")
	for text in (
		f"E-Bilanz {data.YEAR}",
		data.EBILANZ_COMPANY,
		"Aktiva",
		"Passiva",
		data.EBILANZ_BANK,
		data.EBILANZ_NET_INCOME,
		"Kontennachweis",
	):
		expect(preview).to_contain_text(text)


def test_e_bilanz_positionen_opens_a_position_to_its_accounts(desk, expect):
	filters = {"company": data.EBILANZ_COMPANY, "year": data.YEAR, "statement_type": "Jahresabschluss"}
	desk.open(f"{REPORT}?{urlencode(filters)}")
	sales = report_row(desk, "Umsatzerlöse")
	expect(sales).to_have_count(1)
	expect(report_row(desk, "Erlöse 19 % USt")).to_have_count(0)
	sales.locator(".dt-tree-node__toggle").click()
	expect(report_row(desk, "Erlöse 19 % USt")).to_have_count(1)


def test_a_new_e_bilanz_opens_as_a_jahresabschluss_of_the_default_company(desk, expect):
	desk.open(f"{ROUTE}/new")
	expect(desk.field("company").locator("input")).to_have_value(data.COMPANY)
	expect(desk.field("statement_type").locator("select")).to_have_value("Jahresabschluss")
	assert desk.page.evaluate("() => cur_frm.is_new()")
	expect(desk.button("Berechnen")).to_have_count(0)
	expect(desk.button("XBRL exportieren")).to_have_count(0)
