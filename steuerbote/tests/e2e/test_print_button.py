"""Drucken in the print view of a Steuerbote format prints the PDF of the PDF generator, as the button PDF downloads
it: every page with the running head and foot and „Seite n von N“, the table heads repeated. The browser's own print
of the HTML of the print view has neither. Printed here are the Umsatzsteuer-Voranmeldung and the E-Bilanz of the
seed, two and three pages long; their PDFs go through the checks of the print proof (printouts.py).

The module imports neither pytest nor Playwright, see conftest.py.
"""

import shutil
import subprocess

from steuerbote.tests import printouts
from steuerbote.tests.e2e import data
from steuerbote.tests.e2e.test_ebilanz import seeded


def print_with_drucken(desk, expect, route: str, title: str) -> list[printouts.Page]:
	"""Open the print view of the document in its default print format, a format of Steuerbote, and click Drucken."""
	desk.open(route)
	preview = desk.page.locator("iframe").filter(visible=True).content_frame.locator("body")
	expect(preview).to_contain_text(title)
	pdf, opened = desk.printed()
	assert pdf.startswith(b"%PDF"), pdf[:200]
	assert opened == [], f"Drucken opened {opened} instead of printing the PDF"
	expect(desk.page.locator("iframe.print-pdf-frame")).to_have_count(1)
	words = subprocess.run(  # noqa: S603 - Poppler on the PDF the site sent
		[shutil.which("pdftotext") or "pdftotext", "-bbox", "-", "-"],
		input=pdf,
		capture_output=True,
		check=True,
	)
	return printouts.read_bbox(words.stdout.decode("utf-8"))


def assert_paged(pages: list[printouts.Page], name: str, least: int) -> None:
	assert len(pages) >= least, f"{len(pages)} pages, the seed's document fills {least}"
	assert printouts.page_numbers(pages) == []
	assert printouts.on_every_page(pages, [name]) == []


def test_drucken_prints_the_voranmeldung_as_the_pdf_of_the_generator(desk, expect, records):
	name = records["vat_return"]
	pages = print_with_drucken(
		desk, expect, f"/desk/print/VAT Return/{name}", f"Umsatzsteuer-Voranmeldung {data.YEAR}"
	)
	assert_paged(pages, name, 2)


def test_drucken_prints_the_e_bilanz_as_the_pdf_of_the_generator(desk, expect, base_url):
	name = seeded(desk, base_url)
	pages = print_with_drucken(
		desk, expect, f"/desk/print/Electronic Balance Sheet/{name}", f"E-Bilanz {data.YEAR}"
	)
	assert_paged(pages, name, 3)
