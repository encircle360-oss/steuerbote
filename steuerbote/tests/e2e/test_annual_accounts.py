"""The Jahresabschluss of the seed's company of the Jahresabschluss for 2026: the form after Berechnen with the size
class, the Bilanz, the Angaben, the signatories and what holds the Feststellung back; the print preview in Kontoform
with the upload to the Unternehmensregister; the Vorschau der Offenlegung as a PDF at the document; the XBRL, which
waits until the Jahresabschluss could be festgestellt; and a new Jahresabschluss, which opens as a draft of the
default company. The calculated Jahresabschluss is the picture of the README, jahresabschluss.png, under --output.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import json
import re

from steuerbote.tests.e2e import data

DOCTYPE = "Annual Accounts"
ROUTE = "/desk/annual-accounts"
OFFENLEGUNG = "Offenlegung"
# The Angaben of a Kleinstkapitalgesellschaft with an Eigenkapital: Haftungsverhältnisse, Organkredite and the
# zusätzlichen Angaben (steuerbote/hgb/notes.py).
KLEINST_ANGABEN = 3


def seeded(desk, base_url) -> str:
	"""The name of the Jahresabschluss of the seed, which its naming series gives it on the site, read as the desk of the
	test reads it."""
	filters = {"company": data.ACCOUNTS_COMPANY, "year": data.YEAR, "docstatus": 0}
	response = desk.page.request.get(
		f"{base_url}/api/resource/{DOCTYPE}", params={"filters": json.dumps(filters), "fields": '["name"]'}
	)
	assert response.ok, f"{response.url} answered {response.status}: {response.text()[:2000]}"
	names = [row["name"] for row in response.json()["data"]]
	assert len(names) == 1, f"the seed makes one {DOCTYPE} with {filters}, the site has {names}"
	return names[0]


def opened(desk, base_url) -> str:
	name = seeded(desk, base_url)
	desk.open(f"{ROUTE}/{name}")
	return name


def test_berechnen_shows_the_size_class_the_bilanz_the_angaben_and_what_holds_the_feststellung(
	desk, expect, base_url, screenshots
):
	opened(desk, base_url)
	expect(desk.field("status")).to_contain_text("Berechnet")
	expect(desk.field("size_class")).to_contain_text("Kleinst")
	labels = desk.grid_cells("lines", "label")
	expect(labels.filter(has_text=re.compile(r"^\s*Anlagevermögen\s*$"))).to_have_count(1)
	expect(labels.filter(has_text=re.compile(r"^\s*Summe Passiva\s*$"))).to_have_count(1)
	expect(desk.grid_rows("notes")).to_have_count(KLEINST_ANGABEN)
	expect(desk.grid_rows("signatories").filter(has_text=data.ACCOUNTS_DIRECTOR)).to_have_count(1)
	expect(desk.grid_cells("findings", "code").filter(has_text="JA-NICHT-FESTGESTELLT")).to_have_count(1)
	desk.picture(screenshots / "jahresabschluss.png", "lines")


def test_the_print_preview_shows_the_bilanz_in_kontoform_and_the_upload(desk, expect, base_url):
	name = seeded(desk, base_url)
	desk.open(f"/desk/print/{DOCTYPE}/{name}")
	preview = desk.page.locator("iframe").filter(visible=True).content_frame.locator("body")
	expect(preview).to_contain_text(f"Jahresabschluss zum 31.12.{data.YEAR}")
	expect(preview).to_contain_text(data.ACCOUNTS_COMPANY)
	expect(preview).to_contain_text("Summe Aktiva")
	expect(preview).to_contain_text("Summe Passiva")
	expect(preview).to_contain_text("Angaben unter der Bilanz")
	expect(preview).to_contain_text("Upload zum Unternehmensregister")


def test_the_vorschau_der_offenlegung_is_attached_as_a_pdf(desk, expect, base_url):
	opened(desk, base_url)
	response = desk.run_doc_method(
		"make_disclosure_preview", desk.menu_item(OFFENLEGUNG, "Vorschau der Offenlegung").click
	)
	assert response.ok, f"make_disclosure_preview answered {response.status}: {response.text()[:2000]}"
	expect(desk.dialog()).to_contain_text("Die Vorschau der Offenlegung ist angehängt")
	expect(desk.dialog()).to_contain_text(".pdf")


def test_the_xbrl_waits_until_the_jahresabschluss_could_be_festgestellt(desk, expect, base_url):
	name = opened(desk, base_url)
	response = desk.run_doc_method(
		"make_xbrl", desk.menu_item(OFFENLEGUNG, "XBRL für das Unternehmensregister").click
	)
	assert not response.ok
	expect(desk.dialog()).to_contain_text(f"{name} ist nicht bereit")


def test_a_new_jahresabschluss_opens_as_a_draft_of_the_default_company(desk, expect):
	desk.open(f"{ROUTE}/new")
	expect(desk.field("company").locator("input")).to_have_value(data.COMPANY)
	assert desk.page.evaluate("() => cur_frm.is_new()")
	expect(desk.button("Berechnen")).to_have_count(0)
