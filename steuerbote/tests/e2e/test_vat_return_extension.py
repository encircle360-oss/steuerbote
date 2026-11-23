"""The Dauerfristverlängerung of the seed for 2026: no Voranmeldung of 2025 is filed, so Berechnen asks for the
base of the Sondervorauszahlung by hand and leaves the form a draft; and the form of the second company, whose
Senden ELSTER accepted.

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


def test_a_form_elster_accepted_offers_neither_berechnen_nor_verwerfen(desk, expect, records):
	"""ELSTER accepted the Senden of the form of the second company, but submitting it failed: the form keeps all but
	its remarks, so it offers neither Berechnen nor Verwerfen, which the form of the seed offers, and says what is
	left of it instead of how to enter it in Mein ELSTER."""
	desk.open(f"/desk/vat-return-extension/{records['extension']}")
	expect(desk.button("Berechnen")).to_be_visible()
	expect(desk.menu().get_by_role("menuitem", name="Verwerfen", exact=True)).to_be_visible()
	desk.open(f"/desk/vat-return-extension/{records['sent_extension']}")
	expect(desk.message(data.ACCEPTED_NOTE)).to_be_visible()
	expect(desk.message("Mein ELSTER bietet für den Vordruck USt 1 H kein Hochladen an")).to_have_count(0)
	expect(desk.button("Berechnen")).to_have_count(0)
	menu = desk.menu()
	expect(menu.get_by_role("menuitem", name="Neu laden", exact=True)).to_be_visible()
	expect(menu.get_by_role("menuitem", name="Verwerfen", exact=True)).to_have_count(0)
