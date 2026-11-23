"""The setup of Steuerbote: the VAT Return Settings and the mapping of the company of the seed with its check of
the tax templates, and the ERiC Settings, which simulate.

The module imports neither pytest nor Playwright, see conftest.py.
"""

from steuerbote.tests.e2e import data


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
