"""Zuordnung exportieren and Zuordnung importieren for the mapping of the fourth company of the seed: the browser
saves the file under its name, the mapping keeps it as an attachment, and importing it after a change sets the
mapping back.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import json
import re
from pathlib import Path
from urllib.parse import quote

from steuerbote.tests.e2e import data

FILE_NAME = re.compile(r"Kontenzuordnung-Steuerbote-E2E-Zuordnung-GmbH-\d{4}-\d{2}-\d{2}\.json")


def test_a_mapping_exported_and_imported_again_comes_back_as_it_was(desk, expect):
	desk.open(f"/desk/vat-return-mapping/{quote(data.MAPPING_COMPANY)}")
	expect(desk.grid_rows("watched").first).to_be_visible()
	before = levels(desk)
	download = desk.download(desk.menu_item("Datei", "Zuordnung exportieren").click)
	assert FILE_NAME.fullmatch(download.suggested_filename), download.suggested_filename
	text = Path(download.path()).read_text(encoding="utf-8")
	header = json.loads(text)["header"]
	assert (header["format"], header["company"], header["chart"]) == (
		"steuerbote/vat-return-mapping",
		data.MAPPING_COMPANY,
		"SKR03",
	)
	expect(desk.page.locator(".attachment-row")).to_contain_text([download.suggested_filename])
	desk.page.evaluate(
		"""() => {
			const row = cur_frm.doc.watched.find((watched) => watched.account_number === "8603");
			row.level = row.level === "hint" ? "blocking" : "hint";
			cur_frm.dirty();
		}"""
	)
	desk.page.evaluate("() => cur_frm.save()")
	desk.settle()
	assert levels(desk) != before
	desk.menu_item("Datei", "Zuordnung importieren").click()
	desk.wait_for_dialog()
	desk.dialog().locator('textarea[data-fieldname="content"]').fill(text)
	response = desk.run_doc_method("compare_with_file", lambda: desk.answer_dialog(yes=True))
	assert response.ok, response.text()[:2000]
	differences = desk.dialog().filter(has=desk.page.locator("table.steuerbote-differences"))
	expect(differences.locator("tbody tr")).to_have_count(1)
	expect(differences.locator('input.steuerbote-difference[value="account:8603"]')).to_be_checked()
	expect(desk.dialog()).to_have_count(1)
	desk.wait_for_dialog()
	assert desk.run_doc_method("import_file", lambda: desk.answer_dialog(yes=True)).ok
	expect(desk.dialog()).to_have_count(0)
	desk.settle()
	assert levels(desk) == before


def levels(desk) -> list[list[str]]:
	return desk.page.evaluate("() => cur_frm.doc.watched.map((row) => [row.account_number, row.level])")
