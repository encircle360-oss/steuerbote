"""The Umsatzsteuererklärung of the seed for 2026: Berechnen, the note that Mein ELSTER imports no
Umsatzsteuererklärung, the simulated Testsenden and the print preview in the order of form USt 2 A; and a new return,
which opens as a draft of the default company. Berechnen leaves the picture of the README, umsatzsteuererklaerung.png,
under --output.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import json

from steuerbote.tests.e2e import data

DOCTYPE = "Annual VAT Return"
ROUTE = "/desk/annual-vat-return"
# The lines of the invoices of October by their Feldkennungen: the sale at 19 % with its tax (line 24), the § 13b
# service with its tax (line 71), the EU service (line 80) and the Vorsteuer of the § 13b service (line 89).
LINES = ("E3003303", "E3003304", "E3102205", "E3102206", "E3105702", "E3006502")
PERIODS = 12
# Of the Voranmeldungen of the year only that of FILED_MONTH is filed: every other month misses its Voranmeldung.
MISSING_PERIOD = "ZEITRAUM-FEHLT"
MISSING_PERIODS = PERIODS - 1
MEIN_ELSTER_NOTE = "Mein ELSTER importiert keine Umsatzsteuererklärung"


def seeded_return(desk, base_url) -> str:
	"""The name of the return of the seed, which its naming series gives it on the site, read as the desk of the test
	reads it."""
	filters = {"company": data.COMPANY, "year": data.YEAR, "docstatus": 0}
	response = desk.page.request.get(
		f"{base_url}/api/resource/{DOCTYPE}", params={"filters": json.dumps(filters), "fields": '["name"]'}
	)
	assert response.ok, f"{response.url} answered {response.status}: {response.text()[:2000]}"
	names = [row["name"] for row in response.json()["data"]]
	assert len(names) == 1, f"the seed makes one {DOCTYPE} with {filters}, the site has {names}"
	return names[0]


def open_return(desk, base_url) -> str:
	name = seeded_return(desk, base_url)
	desk.open(f"{ROUTE}/{name}")
	return name


def test_berechnen_takes_the_lines_of_the_invoices_and_holds_the_return_for_the_missing_voranmeldungen(
	desk, expect, base_url, screenshots
):
	open_return(desk, base_url)
	desk.calculate()
	expect(desk.field("status")).to_contain_text("Berechnet")
	lines = desk.grid_rows("lines")
	expect(lines).to_have_count(len(LINES))
	for feldkennung in LINES:
		expect(lines.filter(has_text=feldkennung)).to_have_count(1)
	expect(desk.grid_rows("periods")).to_have_count(PERIODS)
	missing = desk.grid_cells("findings", "code").filter(has_text=MISSING_PERIOD)
	expect(missing).to_have_count(MISSING_PERIODS)
	desk.picture(screenshots / "umsatzsteuererklaerung.png", "lines")


def test_the_form_says_that_mein_elster_imports_no_umsatzsteuererklaerung(desk, expect, base_url):
	open_return(desk, base_url)
	expect(desk.message(MEIN_ELSTER_NOTE)).to_be_visible()
	expect(desk.menu_item("ELSTER", "In Mein ELSTER abgegeben")).to_be_visible()


def test_the_simulated_testsenden_asks_first_and_nein_sends_nothing(desk, expect, base_url):
	open_return(desk, base_url)
	desk.menu_item("ELSTER", "Testsenden (Simulation)").click()
	expect(desk.dialog()).to_contain_text("Simulation")
	desk.answer_dialog(yes=False)
	expect(desk.dialog()).to_have_count(0)
	desk.settle()
	assert not desk.called("transmit")


def test_the_print_preview_shows_the_return_in_the_order_of_the_form(desk, expect, base_url):
	name = seeded_return(desk, base_url)
	desk.open(f"/desk/print/{DOCTYPE}/{name}")
	preview = desk.page.locator("iframe").filter(visible=True).content_frame.locator("body")
	expect(preview).to_contain_text(f"Umsatzsteuererklärung {data.YEAR}")
	expect(preview).to_contain_text(data.COMPANY)
	expect(preview).to_contain_text("A. Allgemeine Angaben")
	expect(preview).to_contain_text("Vorauszahlungssoll und Abschlusszahlung")


def test_a_new_return_opens_as_a_draft_of_the_default_company(desk, expect):
	desk.open(f"{ROUTE}/new")
	expect(desk.field("company").locator("input")).to_have_value(data.COMPANY)
	assert desk.page.evaluate("() => cur_frm.is_new()")
	expect(desk.button("Berechnen")).to_have_count(0)
