"""The shortcuts Neue Voranmeldung and Neue ZM, and a new Dauerfristverlängerung: each form opens as a new draft
of the default company, without the buttons of a saved document.

The module imports neither pytest nor Playwright, see conftest.py.
"""

from steuerbote.tests.e2e import data

ROUTES = ("vat-return", "recapitulative-statement", "vat-return-extension")


def test_a_new_document_opens_as_a_draft_of_the_default_company(desk, expect):
	for route in ROUTES:
		desk.open(f"/desk/{route}/new")
		expect(desk.field("company").locator("input")).to_have_value(data.COMPANY)
		assert desk.page.evaluate("() => cur_frm.is_new()"), route
		expect(desk.button("Berechnen")).to_have_count(0)
