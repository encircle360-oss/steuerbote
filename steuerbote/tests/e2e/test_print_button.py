"""Drucken in the print view of a Steuerbote format prints the PDF of the PDF generator, as the button PDF downloads
it: every page with the running head and foot and „Seite n von N“, the table heads repeated. The browser's own print
of the HTML of the print view has neither. Printed here are the Umsatzsteuer-Voranmeldung and the E-Bilanz of the
seed, two and three pages long; their PDFs go through the checks of the print proof (printouts.py). The page
/printview, which a browser prints itself without a generator, gets head and foot from the margin boxes of @page and
its page numbers from the browser; the preview on the screen shows neither.

The module imports neither pytest nor Playwright, see conftest.py.
"""

import shutil
import subprocess
from urllib.parse import urlencode

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
	return pages_of(pdf)


def pages_of(pdf: bytes) -> list[printouts.Page]:
	words = subprocess.run(  # noqa: S603 - Poppler on a PDF of the site
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


def test_the_browser_prints_the_page_printview_with_head_foot_and_page_numbers(desk, expect, records):
	"""Opened by itself, /printview is printed by the browser: Chromium fills the margin boxes of @page."""
	name = records["vat_return"]
	query = {"doctype": "VAT Return", "name": name, "format": "Umsatzsteuer-Voranmeldung", "no_letterhead": 1}
	desk.page.goto(f"/printview?{urlencode(query)}&settings=%7B%7D")
	expect(desk.page.locator(".sb-print")).to_contain_text(f"Umsatzsteuer-Voranmeldung {data.YEAR}")
	desk.page.emulate_media(media="print")
	pages = pages_of(desk.page.pdf(prefer_css_page_size=True, print_background=True))
	assert_paged(pages, name, 2)
	assert printouts.foot_fragments(pages, printouts.Margins(top=28, bottom=18, left=20, right=15)) == []


def test_the_preview_shows_neither_the_running_head_nor_the_foot(desk, expect, records):
	desk.open(f"/desk/print/VAT Return/{records['vat_return']}")
	preview = desk.page.locator("iframe").filter(visible=True).content_frame
	expect(preview.locator("body")).to_contain_text(f"Umsatzsteuer-Voranmeldung {data.YEAR}")
	expect(preview.locator("#footer-html")).to_be_hidden()
	expect(preview.locator("#header-html")).to_be_hidden()
