"""The Umsatzsteuer-Voranmeldung of the seed for October 2026: Berechnen, USt-IdNrn. prüfen, the menu ELSTER, the
file for Mein ELSTER and the print preview; and the form of the return of the second company, whose Senden ELSTER
accepted.

The module imports neither pytest nor Playwright, see conftest.py.
"""

from steuerbote.tests.e2e import data

# The Kennzahlen of the invoices of the seed: the sale at 19 %, the § 13b service, the EU service and Kz 83.
KENNZAHLEN = ["81", "46", "47", "21", "67", "83"]
IMPORT_FILE = f"UStVA_{data.YEAR}_{data.MONTH}.xml"


def open_return(desk, records) -> None:
	desk.open(f"/desk/vat-return/{records['vat_return']}")


def test_berechnen_calculates_the_kennzahlen_of_the_invoices(desk, expect, records):
	open_return(desk, records)
	desk.calculate()
	expect(desk.field("status")).to_contain_text("Bereit")
	kennzahlen = desk.grid_rows("kennzahlen")
	expect(kennzahlen).to_have_count(len(KENNZAHLEN))
	expect(kennzahlen).to_contain_text(KENNZAHLEN)


def test_ust_idnrn_pruefen_stands_next_to_berechnen_and_nein_asks_nobody(desk, expect, records):
	open_return(desk, records)
	expect(desk.button("Berechnen")).to_be_visible()
	desk.button("USt-IdNrn. prüfen").click()
	expect(desk.dialog()).to_contain_text("hinter Kz 41, 42 und 21 des Zeitraums")
	desk.answer_dialog(yes=False)
	expect(desk.dialog()).to_have_count(0)
	desk.settle()
	assert not desk.called("confirm_vat_ids")


def test_the_simulated_testsenden_asks_first_and_nein_sends_nothing(desk, expect, records):
	open_return(desk, records)
	desk.menu_item("ELSTER", "Testsenden (Simulation)").click()
	expect(desk.dialog()).to_contain_text("Simulation")
	desk.answer_dialog(yes=False)
	expect(desk.dialog()).to_have_count(0)
	desk.settle()
	assert not desk.called("transmit")


def test_with_an_eric_runtime_testsenden_asks_for_the_certificate_and_cancel_sends_nothing(
	desk, expect, records
):
	desk.as_if_eric_were_installed()
	open_return(desk, records)
	desk.menu_item("ELSTER", "Testsenden").click()
	dialog = desk.dialog()
	expect(dialog.locator('input[type="file"]')).to_be_visible()
	expect(dialog.locator('input[type="password"]')).to_be_visible()
	desk.close_dialog()
	desk.settle()
	assert not desk.called("transmit")
	assert not [request.url for request in desk.requests if "stash_certificate" in request.url]


def test_xml_fuer_mein_elster_downloads_the_file_and_attaches_it(desk, expect, records):
	open_return(desk, records)
	download = desk.download(desk.button("XML für Mein ELSTER").click)
	assert download.suggested_filename == IMPORT_FILE
	expect(desk.page.locator(".attachment-row")).to_contain_text([IMPORT_FILE])


def test_the_print_preview_shows_the_return_in_its_print_format(desk, expect, records):
	desk.open(f"/desk/print/VAT Return/{records['vat_return']}")
	preview = desk.page.locator("iframe").filter(visible=True).content_frame.locator("body")
	expect(preview).to_contain_text(f"Umsatzsteuer-Voranmeldung {data.YEAR}")
	expect(preview).to_contain_text(data.MONTH_LABEL)
	expect(preview).to_contain_text(data.COMPANY)


def test_a_return_elster_accepted_offers_neither_berechnen_nor_verwerfen(desk, expect, records):
	"""ELSTER accepted the Senden of the return of the second company, but submitting it failed: the return keeps
	all but its remarks, so its form offers neither Berechnen, USt-IdNrn. prüfen nor Verwerfen, which the return of
	the seed offers, and says what is left of it."""
	open_return(desk, records)
	expect(desk.button("Berechnen")).to_be_visible()
	expect(desk.button("USt-IdNrn. prüfen")).to_be_visible()
	expect(desk.menu().get_by_role("menuitem", name="Verwerfen", exact=True)).to_be_visible()
	desk.open(f"/desk/vat-return/{records['sent_vat_return']}")
	expect(desk.message(data.ACCEPTED_NOTE)).to_be_visible()
	for label in ("Berechnen", "USt-IdNrn. prüfen"):
		expect(desk.button(label)).to_have_count(0)
	menu = desk.menu()
	expect(menu.get_by_role("menuitem", name="Neu laden", exact=True)).to_be_visible()
	expect(menu.get_by_role("menuitem", name="Verwerfen", exact=True)).to_have_count(0)
