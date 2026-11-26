"""The dialog of Vorgaben aktualisieren and of Zuordnung importieren at the width of a common laptop screen: since
the positions of the Bilanzzuordnung carry their labels, a row holds long texts and element names without spaces,
which may not push the last columns out of the dialog (R3-F-08).

The module imports neither pytest nor Playwright, see conftest.py.
"""

import json
from urllib.parse import quote

from steuerbote.tests.e2e import data
from steuerbote.tests.e2e.desk import doc_method

LAPTOP = {"width": 1366, "height": 768}
POSITION = (
	"Position Forderungen und sonstige Vermögensgegenstände, sonstige Vermögensgegenstände, "
	"Umsatzsteuerforderungen (bs.ass.currAss.receiv.other.vat), opposite balance Verbindlichkeiten, sonstige "
	"Verbindlichkeiten, davon aus Steuern (bs.eqLiab.liab.other.theroffTax), both"
)


def test_the_differences_fit_into_their_dialog_at_1366_pixels(desk, expect):
	"""The answer of compare_with_defaults is fixed here, a row with the longest texts the Bilanzzuordnung gives, so
	that the test measures the dialog and not the defaults of the day."""
	comparison = {
		"version": "SKR04 Taxonomie 6.9 2026.5",
		"taken_over": "SKR04 Taxonomie 6.9 2026.4",
		"base_known": True,
		"differences": [
			{
				"id": "account:1401",
				"subject": "Konto 1401",
				"change": "Ändert sich",
				"fields": "Position, Gegensaldo",
				"current": POSITION,
				"proposed": POSITION,
				"origin": "Vorgabe geändert",
				"proposes": True,
			}
		],
		"unchanged": 12,
	}

	def answer(route):
		if doc_method(route.request) == "compare_with_defaults":
			route.fulfill(
				status=200, content_type="application/json", body=json.dumps({"message": comparison})
			)
		else:
			route.continue_()

	desk.page.set_viewport_size(LAPTOP)
	desk.open(f"/desk/balance-sheet-mapping/{quote(data.EBILANZ_COMPANY)}")
	desk.page.route("**/api/method/run_doc_method", answer)
	desk.button("Vorgaben aktualisieren").click()
	dialog = desk.dialog()
	expect(dialog.locator("table.steuerbote-differences")).to_be_visible()
	box = dialog.locator(".modal-content").bounding_box()
	for cell in (dialog.locator("thead th").last, dialog.locator("tbody td").last):
		edge = cell.bounding_box()
		assert edge["x"] + edge["width"] <= box["x"] + box["width"], "the last column runs out of the dialog"
	desk.close_dialog()
	desk.page.unroute("**/api/method/run_doc_method")
