"""The setup of Steuerbote: Steuerbote einrichten for the third company of the seed, the VAT Return Settings and the
mapping of the company of the seed with its check of the tax templates, Vorgaben aktualisieren for the mapping of the
fourth company, and the ERiC Settings, which simulate. The first run of Steuerbote einrichten leaves the picture of
the README, steuerbote-einrichten.png, under --output.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import re
from urllib.parse import quote

from steuerbote.tests.e2e import data

SETUP_METHOD = "steuerbote.steuerbote.setup.set_up"


def test_the_settings_show_their_rules_in_their_tables(desk, expect):
	desk.open(f"/desk/vat-return-settings/{data.COMPANY}")
	for table in ("period_rules", "prepayments", "zm_rules"):
		rows = desk.grid_rows(table)
		expect(rows).to_have_count(1)
		expect(rows).to_contain_text([str(data.YEAR)])


def test_vorgaben_laden_replaces_the_rules_with_the_defaults_of_skr03(desk, expect):
	"""The seed made the mapping with the same defaults, so the rules come back as they were, unsaved, and the
	column Steuersatz shows them as before: a rule without a rate holds 0, which the column leaves blank."""
	desk.open(f"/desk/vat-return-mapping/{data.COMPANY}")
	expect(desk.grid_rows("rules").first).to_be_visible()
	before = rules_of(desk)
	expect(desk.grid_rows("rules")).to_have_count(len(before))
	rates = desk.grid_cells("rules", "tax_rate")
	shown = rates.all_text_contents()
	assert [not text.strip() for text in shown] == [not rule[3] for rule in before]
	assert any(rule[3] for rule in before) and not all(rule[3] for rule in before)
	desk.button("Vorgaben laden").click()
	response = desk.run_doc_method("load_defaults", lambda: desk.answer_dialog(yes=True))
	assert response.ok
	expect(desk.dialog()).to_contain_text("Vorgaben geladen")
	desk.close_dialog()
	expect(desk.grid_rows("rules")).to_have_count(len(before))
	assert rules_of(desk) == before
	expect(rates).to_have_text(shown)
	assert desk.page.evaluate("() => cur_frm.is_dirty()")


def test_steuervorlagen_pruefen_finds_every_account_of_the_templates_in_the_mapping(desk, expect):
	"""The company of the seed has no tax templates of its own, so no account of them lacks a place."""
	desk.open(f"/desk/vat-return-mapping/{data.COMPANY}")
	expect(desk.grid_rows("rules").first).to_be_visible()
	response = desk.run_doc_method("check_tax_templates", desk.button("Steuervorlagen prüfen").click)
	assert response.ok
	expect(desk.dialog()).to_contain_text(
		"Jedes Konto der Steuervorlagen hat einen Platz in der Kontenzuordnung."
	)
	desk.close_dialog()


def rules_of(desk) -> list[list]:
	return desk.page.evaluate(
		"() => cur_frm.doc.rules.map((rule) => [rule.account, rule.kennzahl, rule.side, rule.tax_rate || 0])"
	)


def test_the_eric_settings_say_that_they_simulate(desk, expect):
	desk.open("/desk/eric-settings")
	expect(desk.page.locator(".form-message")).to_contain_text("Simulationsmodus")
	assert desk.page.evaluate("() => cur_frm.doc.simulation") == 1
	expect(desk.button("Laufzeitumgebung installieren")).to_be_visible()


def test_steuerbote_einrichten_sets_up_a_company_once(desk, expect, screenshots):
	"""The first run makes the settings and the mappings with the defaults of SKR03 and leaves the
	Voranmeldungszeitraum open; the second changes nothing and says so."""
	desk.open(f"/desk/steuerbote-setup?company={quote(data.SETUP_COMPANY)}")
	remove_what_a_run_set_up(desk, data.SETUP_COMPANY)
	expect(desk.field("company").locator("input")).to_have_value(data.SETUP_COMPANY)
	report = desk.page.locator(".steuerbote-setup-report")
	set_up(desk)
	expect(report.locator(".steuerbote-setup-summary")).to_contain_text(
		f"Steuerbote ist für {data.SETUP_COMPANY} eingerichtet."
	)
	expect(report.locator("tbody tr")).to_have_count(7)
	for step, outcome in (
		("vat_return_settings", "Angelegt"),
		("vat_return_mapping", "Angelegt"),
		("filing_period", "Offen"),
		("books_start", "Übersprungen"),
		("deadlines", "Offen"),
		("income_tax_mapping", "Angelegt"),
		("balance_sheet_mapping", "Angelegt"),
	):
		expect(report.locator(f'tr[data-step="{step}"]')).to_contain_text(outcome)
	expect(report.locator('tr[data-step="vat_return_mapping"]')).to_contain_text("SKR03")
	desk.picture(screenshots / "steuerbote-einrichten.png")
	set_up(desk)
	expect(report.locator(".steuerbote-setup-summary")).to_contain_text(
		f"Nichts geändert: {data.SETUP_COMPANY} war schon eingerichtet."
	)
	for step in ("vat_return_settings", "vat_return_mapping", "income_tax_mapping", "balance_sheet_mapping"):
		expect(report.locator(f'tr[data-step="{step}"]')).to_contain_text("Übersprungen")
	report.locator('tr[data-step="vat_return_mapping"] a').click()
	expect(desk.page).to_have_url(re.compile(r"/desk/vat-return-mapping/"))
	for table, count in data.SETUP_MAPPING.items():
		expect(desk.grid_rows(table)).to_have_count(count)


def set_up(desk) -> None:
	"""Einrichten, and wait until the page shows what the server answered."""
	with desk.page.expect_response(lambda response: SETUP_METHOD in response.url) as answer:
		desk.button("Einrichten").click()
	assert answer.value.ok, f"{SETUP_METHOD} answered {answer.value.status}: {answer.value.text()[:2000]}"
	desk.settle()


def remove_what_a_run_set_up(desk, company: str) -> None:
	"""Delete the mappings and the settings of the company if an earlier run of the tests made them."""
	desk.page.evaluate(
		"""async (company) => {
			for (const doctype of [
				"Balance Sheet Mapping",
				"Income Tax Mapping",
				"VAT Return Mapping",
				"VAT Return Settings",
			]) {
				if (await frappe.db.exists(doctype, company)) {
					await frappe.db.delete_doc(doctype, company);
				}
			}
		}""",
		company,
	)
	desk.settle()


def test_vorgaben_aktualisieren_proposes_the_changes_of_the_defaults_and_keeps_your_own(desk, expect):
	"""Vorgaben laden sets the mapping of the fourth company back; then it looks as if older defaults had mapped 8400
	to Kz 86 and the user had set 1548 to the level Hinweis. The dialog checks the change of the defaults and leaves
	the user's own unchecked, its button says how many differences a click takes over, or with none checked that it
	notes the defaults as seen, and taking over the checked one changes 8400 alone."""
	desk.open(f"/desk/vat-return-mapping/{quote(data.MAPPING_COMPANY)}")
	expect(desk.grid_rows("rules").first).to_be_visible()
	desk.button("Vorgaben laden").click()
	assert desk.run_doc_method("load_defaults", lambda: desk.answer_dialog(yes=True)).ok
	expect(desk.dialog()).to_contain_text("Vorgaben geladen")
	desk.close_dialog()
	save(desk)
	desk.page.evaluate(
		"""() => {
			const rows = JSON.parse(cur_frm.doc.defaults_rows);
			rows.rules.find((rule) => rule.account_number === "8400").kennzahl = "86";
			cur_frm.doc.defaults_rows = JSON.stringify(rows);
			cur_frm.doc.rules.find((rule) => rule.account_number === "8400").kennzahl = "86";
			cur_frm.doc.watched.find((row) => row.account_number === "1548").level = "hint";
			cur_frm.dirty();
		}"""
	)
	save(desk)
	response = desk.run_doc_method("compare_with_defaults", desk.button("Vorgaben aktualisieren").click)
	assert response.ok
	dialog = desk.dialog()
	expect(dialog.locator("tbody tr")).to_have_count(2)
	expect(dialog.locator('input.steuerbote-difference[value="account:8400"]')).to_be_checked()
	expect(dialog.locator('input.steuerbote-difference[value="account:1548"]')).not_to_be_checked()
	expect(dialog).to_contain_text("Vorgabe geändert")
	expect(dialog).to_contain_text("Eigene Änderung")
	button = dialog.locator(".btn-modal-primary")
	expect(button).to_have_text("1 Unterschied übernehmen")
	dialog.locator('input.steuerbote-difference[value="account:8400"]').uncheck()
	expect(button).to_have_text("Keinen übernehmen und die Vorgaben SKR03 2026.3 als gesehen vermerken")
	dialog.locator("input.steuerbote-all-differences").check()
	expect(button).to_have_text("2 Unterschiede übernehmen")
	dialog.locator('input.steuerbote-difference[value="account:1548"]').uncheck()
	expect(button).to_have_text("1 Unterschied übernehmen")
	assert desk.run_doc_method("update_from_defaults", lambda: desk.answer_dialog(yes=True)).ok
	expect(dialog).to_have_count(0)
	desk.settle()
	assert desk.page.evaluate(
		"""() => [
			cur_frm.doc.rules.find((rule) => rule.account_number === "8400").kennzahl,
			cur_frm.doc.watched.find((row) => row.account_number === "1548").level,
			cur_frm.doc.defaults_version,
		]"""
	) == ["81", "hint", "SKR03 2026.3"]


def save(desk) -> None:
	"""Save the form as Strg+S does, and wait until the desk has the answer."""
	desk.page.evaluate("() => cur_frm.save()")
	desk.settle()
	assert not desk.page.evaluate("() => cur_frm.is_dirty()")
