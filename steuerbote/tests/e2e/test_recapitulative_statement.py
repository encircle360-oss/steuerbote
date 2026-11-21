"""The Zusammenfassende Meldung of the seed for October 2026: Berechnen and the file for Mein ELSTER.

The module imports neither pytest nor Playwright, see conftest.py.
"""

from steuerbote.tests.e2e import data


def open_statement(desk, records) -> None:
	desk.open(f"/desk/recapitulative-statement/{records['statement']}")


def test_berechnen_reports_the_service_to_the_eu_customer_in_one_line(desk, expect, records):
	open_statement(desk, records)
	desk.calculate()
	expect(desk.field("status")).to_contain_text("Bereit")
	lines = desk.grid_rows("lines")
	expect(lines).to_have_count(1)
	expect(lines).to_contain_text([data.EU_VAT_ID])


def test_csv_fuer_mein_elster_downloads_the_file_and_attaches_it(desk, expect, records):
	open_statement(desk, records)
	download = desk.download(desk.button("CSV für Mein ELSTER").click)
	assert download.suggested_filename.endswith(".csv")
	expect(desk.page.locator(".attachment-row")).to_contain_text([download.suggested_filename])
