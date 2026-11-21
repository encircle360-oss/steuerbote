"""Every list of the sidebar Steuerbote opens and shows the records of the seed, filtered by its company.

The module imports neither pytest nor Playwright, see conftest.py, which runs test_the_list_opens once for each
list of LISTS.
"""

from urllib.parse import quote

from steuerbote.tests.e2e import data

# The route of each list and what its rows show, one text per row.
LISTS = {
	"vat-return": [data.MONTH_LABEL, "September 2026"],
	"vat-return-extension": [data.COMPANY],
	"recapitulative-statement": [data.MONTH_LABEL],
	"vat-id-confirmation": [data.EU_VAT_ID],
	"vat-return-mapping": [data.COMPANY],
	"vat-return-settings": [data.COMPANY],
	"elster-transmission": ["Erfolgreich"],
	"deadline-reminder": [],
}


def test_the_list_opens(desk, expect, list_view):
	route, texts = list_view
	desk.open(f"/desk/{route}?company={quote(data.COMPANY)}")
	expect(desk.page.locator(".frappe-list")).to_be_visible()
	rows = desk.list_rows()
	expect(rows).to_have_count(len(texts))
	if texts:
		expect(rows).to_contain_text(texts)
