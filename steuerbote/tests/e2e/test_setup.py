"""The setup of Steuerbote: Steuerbote einrichten for the third company of the seed, the VAT Return Settings and the
mapping of the company of the seed with its check of the tax templates, and the ERiC Settings, which simulate.

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


def test_steuerbote_einrichten_sets_up_a_company_once(desk, expect):
	"""The first run makes the settings and the mapping with the defaults of SKR03 and leaves the
	Voranmeldungszeitraum open; the second changes nothing and says so."""
	desk.open(f"/desk/steuerbote-setup?company={quote(data.SETUP_COMPANY)}")
	remove_what_a_run_set_up(desk, data.SETUP_COMPANY)
	expect(desk.field("company").locator("input")).to_have_value(data.SETUP_COMPANY)
	report = desk.page.locator(".steuerbote-setup-report")
	set_up(desk)
	expect(report.locator(".steuerbote-setup-summary")).to_contain_text(
		f"Steuerbote ist für {data.SETUP_COMPANY} eingerichtet."
	)
	expect(report.locator("tbody tr")).to_have_count(3)
	for step, outcome in (
		("vat_return_settings", "Angelegt"),
		("vat_return_mapping", "Angelegt"),
		("filing_period", "Offen"),
	):
		expect(report.locator(f'tr[data-step="{step}"]')).to_contain_text(outcome)
	expect(report.locator('tr[data-step="vat_return_mapping"]')).to_contain_text("SKR03")
	set_up(desk)
	expect(report.locator(".steuerbote-setup-summary")).to_contain_text(
		f"Nichts geändert: {data.SETUP_COMPANY} war schon eingerichtet."
	)
	for step in ("vat_return_settings", "vat_return_mapping"):
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
	"""Delete the mapping and the settings of the company if an earlier run of the tests made them."""
	desk.page.evaluate(
		"""async (company) => {
			for (const doctype of ["VAT Return Mapping", "VAT Return Settings"]) {
				if (await frappe.db.exists(doctype, company)) {
					await frappe.db.delete_doc(doctype, company);
				}
			}
		}""",
		company,
	)
	desk.settle()
