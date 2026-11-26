"""The dialog of Vorgaben aktualisieren and of Zuordnung importieren at the width of a common laptop screen: since
the positions of the Bilanzzuordnung carry their labels, a row holds long texts and element names without spaces,
which may not push the last columns out of the dialog (R3-F-08).

The module imports neither pytest nor Playwright, see conftest.py.
"""

from urllib.parse import quote

from steuerbote.tests.e2e import data

LAPTOP = {"width": 1366, "height": 768}
POSITION = (
	"Position Forderungen und sonstige Vermögensgegenstände, sonstige Vermögensgegenstände, "
	"Umsatzsteuerforderungen (bs.ass.currAss.receiv.other.vat), opposite balance Verbindlichkeiten, sonstige "
	"Verbindlichkeiten, davon aus Steuern (bs.eqLiab.liab.other.theroffTax), both"
)


def test_the_differences_fit_into_their_dialog_at_1366_pixels(desk, expect):
	desk.page.set_viewport_size(LAPTOP)
	desk.open(f"/desk/balance-sheet-mapping/{quote(data.EBILANZ_COMPANY)}")
	desk.page.evaluate(
		"""(position) => show_mapping_differences({
			title: "Vorgaben aktualisieren",
			intro: "Diese Zeilen weichen von den Vorgaben ab.",
			differences: [{
				id: "account:1401",
				subject: "Konto 1401",
				change: "Ändert sich",
				fields: "Position, Gegensaldo",
				current: position,
				proposed: position,
				origin: "Vorgabe geändert",
				proposes: true,
			}],
			unchanged: 12,
			subject_label: "Konto",
			proposed_label: "Vorgaben SKR04 Taxonomie 6.9 2026.5",
			show_origin: true,
			apply_label: "1 Unterschied übernehmen",
			apply: () => {},
		})""",
		POSITION,
	)
	dialog = desk.dialog()
	expect(dialog.locator("table.steuerbote-differences")).to_be_visible()
	box = dialog.locator(".modal-content").bounding_box()
	for cell in (dialog.locator("thead th").last, dialog.locator("tbody td").last):
		edge = cell.bounding_box()
		assert edge["x"] + edge["width"] <= box["x"] + box["width"], "the last column runs out of the dialog"
	desk.close_dialog()
