"""The Dauerfristverlängerung of the seed for 2026: no Voranmeldung of 2025 is filed, so Berechnen asks for the
base of the Sondervorauszahlung by hand and leaves the form a draft.

The module imports neither pytest nor Playwright, see conftest.py.
"""

from steuerbote.tests.e2e import data

# HTTP 417 is how Frappe answers a message of frappe.throw.
REFUSED = 417


def test_berechnen_asks_for_the_base_by_hand_without_a_filed_voranmeldung_of_the_year_before(
	desk, expect, records
):
	desk.open(f"/desk/vat-return-extension/{records['extension']}")
	response = desk.run_doc_method("calculate", desk.button("Berechnen").click)
	assert response.status == REFUSED
	expect(desk.dialog()).to_contain_text(
		f"{data.COMPANY} hat keine Voranmeldung für {data.YEAR - 1} abgegeben"
	)
	desk.close_dialog()
	expect(desk.field("status")).to_contain_text("Entwurf")
