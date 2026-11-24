"""The links between the annual documents of the seed in the desk: the E-Bilanz of the company of the E-Bilanz names
the Jahresabschluss of its year, opens it and hints that it is not calculated, the Jahresabschluss lists the E-Bilanz
among its connections, and the Körperschaftsteuererklärung names the E-Bilanz and opens it from its field; the
Umsatzsteuererklärung of the company of the Umsatzerlöse shows the hint that the Umsatzerlöse of its filed E-Bilanz
are not its sales.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import json
import re

from steuerbote.tests.e2e import data

ACCOUNTS = "Annual Accounts"
EBILANZ = "Electronic Balance Sheet"
CORPORATE = "Corporate Income Tax Return"
VAT = "Annual VAT Return"
ROUTES = {
	ACCOUNTS: "/desk/annual-accounts",
	EBILANZ: "/desk/electronic-balance-sheet",
	CORPORATE: "/desk/corporate-income-tax-return",
	VAT: "/desk/annual-vat-return",
}


def form_url(doctype: str, name: str) -> re.Pattern[str]:
	"""The address of the form of a document, which the desk may give the module of the sidebar in front of it."""
	route = ROUTES[doctype].removeprefix("/desk/")
	return re.compile(rf"/desk/(steuerbote/)?{route}/{re.escape(name)}$")


def seeded(desk, base_url, doctype: str, company: str, docstatus: int = 0) -> str:
	"""The name of the document of the seed, which its naming series gives it on the site."""
	filters = {"company": company, "year": data.YEAR, "docstatus": docstatus}
	response = desk.page.request.get(
		f"{base_url}/api/resource/{doctype}", params={"filters": json.dumps(filters), "fields": '["name"]'}
	)
	assert response.ok, f"{response.url} answered {response.status}: {response.text()[:2000]}"
	names = [row["name"] for row in response.json()["data"]]
	assert len(names) == 1, f"the seed makes one {doctype} with {filters}, the site has {names}"
	return names[0]


def opened(desk, base_url, doctype: str, company: str) -> str:
	name = seeded(desk, base_url, doctype, company)
	desk.open(f"{ROUTES[doctype]}/{name}")
	return name


def test_the_e_bilanz_names_its_jahresabschluss_and_opens_it(desk, expect, base_url):
	accounts = seeded(desk, base_url, ACCOUNTS, data.EBILANZ_COMPANY)
	opened(desk, base_url, EBILANZ, data.EBILANZ_COMPANY)
	expect(desk.grid_cells("findings", "code").filter(has_text=data.INTERPLAY_HINT)).to_have_count(1)
	link = desk.field("annual_accounts").get_by_role("link", name=accounts)
	expect(link).to_be_visible()
	link.click()
	expect(desk.page).to_have_url(form_url(ACCOUNTS, accounts))
	expect(desk.field("company").locator("input")).to_have_value(data.EBILANZ_COMPANY)


def test_the_jahresabschluss_lists_the_e_bilanz_among_its_connections(desk, expect, base_url):
	opened(desk, base_url, ACCOUNTS, data.EBILANZ_COMPANY)
	connection = desk.page.locator(f'.form-documents .document-link[data-doctype="{EBILANZ}"]')
	expect(connection.locator(".badge-link")).to_have_text("E-Bilanz")
	expect(connection.locator(".count")).to_have_text("1")


def test_the_koerperschaftsteuererklaerung_names_the_e_bilanz_and_opens_it(desk, expect, base_url):
	"""The field shows the button that opens the document it names while the pointer is on it."""
	ebilanz = seeded(desk, base_url, EBILANZ, data.EBILANZ_COMPANY)
	opened(desk, base_url, CORPORATE, data.EBILANZ_COMPANY)
	field = desk.field("electronic_balance_sheet")
	expect(field.locator("input")).to_have_value(ebilanz)
	field.locator("input").hover()
	field.locator(".btn-open").click()
	expect(desk.page).to_have_url(form_url(EBILANZ, ebilanz))
	expect(desk.field("company").locator("input")).to_have_value(data.EBILANZ_COMPANY)


def test_the_umsatzsteuererklaerung_hints_that_the_umsatzerloese_are_not_its_sales(desk, expect, base_url):
	ebilanz = seeded(desk, base_url, EBILANZ, data.REVENUE_COMPANY, docstatus=1)
	opened(desk, base_url, VAT, data.REVENUE_COMPANY)
	hint = desk.grid_rows("findings").filter(has_text=data.REVENUE_HINT)
	expect(hint).to_have_count(1)
	expect(hint).to_contain_text("Hinweis")
	for text in (ebilanz, f"{data.REVENUE_EBILANZ}.00", f"{data.REVENUE_SALES}.00", "24"):
		expect(hint).to_contain_text(text)
