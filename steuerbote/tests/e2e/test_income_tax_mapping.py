"""The Income Tax Mapping in the browser: Vorgaben laden for the company of the seed, whose ledger has none of the
accounts the defaults of SKR03 name, leaves the tables empty and lists the DATEV accounts the company lacks with their
labels; and a mapping without rows that has not taken over the defaults of today names them above its fields.

The module imports neither pytest nor Playwright, see conftest.py.
"""

from urllib.parse import quote

from steuerbote.tests.e2e import data

MAPPING = "Income Tax Mapping"


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
	assert desk.page.evaluate("() => cur_frm.doc.defaults_version") == "SKR03 2026.4"


def test_a_mapping_without_rows_names_the_defaults_until_vorgaben_laden_takes_them_over(desk, expect):
	"""A mapping of the fourth company of the seed, made without rows as by hand, names the defaults of today above its
	fields; once Vorgaben laden has taken them over, it names none, although the company has none of their accounts."""
	desk.open("/desk/income-tax-mapping")
	remove_mapping(desk, data.MAPPING_COMPANY)
	try:
		desk.page.evaluate(
			"(company) => frappe.db.insert({ doctype: 'Income Tax Mapping', company, chart: 'SKR03' })",
			data.MAPPING_COMPANY,
		)
		desk.open(f"/desk/income-tax-mapping/{quote(data.MAPPING_COMPANY)}")
		hint = desk.message("Diese Zuordnung hat keine Zeilen.")
		expect(hint).to_contain_text("„Vorgaben laden“ holt die Vorgaben SKR03 2026.4.")
		response = desk.run_doc_method("load_defaults", desk.button("Vorgaben laden").click)
		assert response.ok, response.text()[:2000]
		desk.close_dialog()
		expect(hint).to_have_count(0)
		assert desk.page.evaluate("() => cur_frm.doc.defaults_version") == "SKR03 2026.4"
	finally:
		remove_mapping(desk, data.MAPPING_COMPANY)


def remove_mapping(desk, company: str) -> None:
	"""Delete the Income Tax Mapping of the company if the seed or an earlier run of the tests left one."""
	desk.page.evaluate(
		"""async ([doctype, company]) => {
			if (await frappe.db.exists(doctype, company)) {
				await frappe.db.delete_doc(doctype, company);
			}
		}""",
		[MAPPING, company],
	)
	desk.settle()
