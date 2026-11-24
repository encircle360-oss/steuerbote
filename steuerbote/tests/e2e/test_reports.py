"""The reports UStVA Kennzahlen and Offene Fristen with the data of the seed; each leaves its picture of the README,
bericht-kennzahlen.png with the vouchers of every Kennzahl and offene-fristen.png, under --output.

The module imports neither pytest nor Playwright, see conftest.py.
"""

from urllib.parse import urlencode

from steuerbote.tests.e2e import data

KENNZAHLEN = "/desk/query-report/UStVA Kennzahlen"
FILTERS = {"company": data.COMPANY, "year": data.YEAR, "rhythm": "monthly", "period_index": data.MONTH}
REPORT_RUN = "/api/method/frappe.desk.query_report.run"
PRINT_LINK = f"/printview?doctype=Sales%20Invoice&name={data.DOMESTIC_INVOICE}"
# Alle ausklappen below the table of a report with a tree (frappe/public/js/frappe/views/reports/query_report.js).
EXPAND_ALL = '[data-action="expand_all_rows"]'


def report_row(desk, text: str):
	"""The row of the report's table that shows the text."""
	return desk.page.locator(".dt-scrollable .dt-row").filter(has_text=text)


def test_ustva_kennzahlen_shows_the_vouchers_behind_a_kennzahl_with_their_print_link(
	desk, expect, screenshots
):
	desk.open(f"{KENNZAHLEN}?{urlencode(FILTERS)}")
	kz81 = report_row(desk, "Steuerpflichtige Umsätze zum Steuersatz von 19 %")
	expect(kz81).to_have_count(1)
	expect(report_row(desk, data.DOMESTIC_INVOICE)).to_have_count(0)
	kz81.locator(".dt-tree-node__toggle").click()
	voucher = report_row(desk, data.DOMESTIC_INVOICE)
	expect(voucher).to_have_count(1)
	expect(voucher).to_contain_text(data.DOMESTIC_CUSTOMER)
	expect(voucher.get_by_role("link", name="Drucken")).to_have_attribute("href", PRINT_LINK)
	desk.page.locator(EXPAND_ALL).click()
	desk.picture(screenshots / "bericht-kennzahlen.png")


def test_the_filters_of_ustva_kennzahlen_choose_the_period(desk, expect):
	desk.open(f"{KENNZAHLEN}?{urlencode(FILTERS)}")
	kz21 = report_row(desk, "Nicht steuerbare sonstige Leistungen")
	expect(kz21).to_have_count(1)
	with desk.page.expect_response(lambda response: REPORT_RUN in response.url) as answer:
		period = desk.field("period_index").locator("input")
		period.fill(str(data.FILED_MONTH))
		period.press("Tab")
	assert answer.value.ok
	expect(kz21).to_have_count(0)


def test_offene_fristen_lists_the_deadlines_of_the_company(desk, expect, screenshots):
	desk.open(f"/desk/query-report/Offene Fristen?{urlencode({'company': data.COMPANY})}")
	rows = desk.page.locator(".dt-scrollable .dt-row")
	expect(rows.first).to_be_visible()
	expect(rows.first).to_contain_text(data.COMPANY)
	desk.picture(screenshots / "offene-fristen.png")
