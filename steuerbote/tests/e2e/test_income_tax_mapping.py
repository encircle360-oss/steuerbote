"""The Income Tax Mapping in the browser: Vorgaben laden for the company of the seed, whose ledger has none of the
accounts the defaults of SKR03 name, leaves the tables empty and lists the DATEV accounts the company lacks with their
labels.

The module imports neither pytest nor Playwright, see conftest.py.
"""

from steuerbote.tests.e2e import data


def test_vorgaben_laden_names_the_datev_accounts_the_company_lacks(desk, expect):
	desk.open("/desk/income-tax-mapping/new")
	desk.page.evaluate("(company) => cur_frm.set_value('company', company)", data.COMPANY)
	desk.settle()
	expect(desk.field("rules")).to_contain_text("Kategorie")
	response = desk.run_doc_method("load_defaults", desk.button("Vorgaben laden").click)
	assert response.ok, response.text()[:2000]
	desk.wait_for_dialog()
	expect(desk.dialog()).to_contain_text("Vorgaben geladen")
	missing = desk.dialog().locator("table.steuerbote-missing-accounts tbody tr")
	expect(missing.first).to_contain_text("2004")
	expect(missing.filter(has_text="Körperschaftsteuer für Vorjahre")).to_contain_text("2203")
	desk.close_dialog()
	assert desk.page.evaluate("() => [cur_frm.doc.rules.length, cur_frm.doc.watched.length]") == [0, 0]
	assert desk.page.evaluate("() => cur_frm.doc.defaults_version") == "SKR03 2026.1"
