"""The Zusammenfassende Meldung of the seed for October 2026: Berechnen and the file for Mein ELSTER; and the form
of the statement of the second company, whose Senden has an unknown outcome.

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


def test_a_statement_whose_senden_has_an_unknown_outcome_offers_neither_berechnen_nor_verwerfen(
	desk, expect, records
):
	"""Whether the statement of the second company reached ELSTER is unknown: it keeps all but its remarks, so its
	form offers neither Berechnen, USt-IdNrn. prüfen nor Verwerfen, which the statement of the seed offers, but
	still the notes of its filing, and says what to check instead of what the buttons do."""
	open_statement(desk, records)
	expect(desk.button("Berechnen")).to_be_visible()
	expect(desk.button("USt-IdNrn. prüfen")).to_be_visible()
	expect(desk.menu().get_by_role("menuitem", name="Verwerfen", exact=True)).to_be_visible()
	statement = records["sent_statement"]
	desk.open(f"/desk/recapitulative-statement/{statement}")
	unknown = f"bei ELSTER angekommen ist, ist unbekannt, deshalb bleibt der Beleg {statement}, wie er gesendet wurde."
	expect(desk.message(unknown)).to_be_visible()
	expect(desk.message("liest das Hauptbuch der Monate des Meldezeitraums")).to_have_count(0)
	for label in ("Berechnen", "USt-IdNrn. prüfen"):
		expect(desk.button(label)).to_have_count(0)
	expect(desk.menu_item("ELSTER", "In Mein ELSTER abgegeben")).to_be_visible()
	desk.page.keyboard.press("Escape")
	menu = desk.menu()
	expect(menu.get_by_role("menuitem", name="Neu laden", exact=True)).to_be_visible()
	expect(menu.get_by_role("menuitem", name="Verwerfen", exact=True)).to_have_count(0)
