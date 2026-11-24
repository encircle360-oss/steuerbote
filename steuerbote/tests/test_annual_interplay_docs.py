"""docs/jahresmeldungen.md says how the annual documents of a year feed each other, read without a bench: the section
„Zusammenspiel der Jahresmeldungen“ names every field that links two of them and every finding of their comparisons,
gives the order of the work of a year, links the pages of the documents and is linked by them, and the architecture
names its modules."""

import re
from pathlib import Path
from unittest import TestCase

from steuerbote.steuerbote.doctype.annual_vat_return import revenue
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge as income_tax
from steuerbote.steuerbote.doctype.electronic_balance_sheet import comparison

APP = Path(__file__).resolve().parents[1]
DOCS = APP.parent / "docs"
PAGE = DOCS / "jahresmeldungen.md"
HEADING = "## Zusammenspiel der Jahresmeldungen"
TARGET = "jahresmeldungen.md#zusammenspiel-der-jahresmeldungen"
PAGES = ("ertragsteuern.md", "ebilanz.md", "jahresabschluss.md", "umsatzsteuererklaerung.md")
LINK = re.compile(r"\]\(([^)\s]+)\)")
TITLE = re.compile(r"^#{1,6} (.+)$", re.MULTILINE)
STEP = re.compile(r"^\d+\. \*\*([^:*]+):\*\*", re.MULTILINE)


def section() -> str:
	text = PAGE.read_text(encoding="utf-8")
	return text.split(f"{HEADING}\n", 1)[1].split("\n## ", 1)[0]


def anchors(text: str) -> set[str]:
	"""The anchors of the headings of a page, as GitHub writes them."""
	return {re.sub(r"[^\w\- ]", "", title.strip().lower()).replace(" ", "-") for title in TITLE.findall(text)}


class InterplayDocsTest(TestCase):
	def test_the_section_stands_before_the_part_for_the_modules(self):
		text = PAGE.read_text(encoding="utf-8")
		self.assertLess(text.index(HEADING), text.index("## Für die Module"))

	def test_names_every_link_and_every_finding_of_the_comparisons(self):
		names = set(re.findall(r"`([^`]+)`", section()))
		codes = {
			income_tax.EBILANZ_DIFFERS,
			income_tax.UEBERLEITUNG_TWICE,
			income_tax.EQUITY_SOURCE,
			*comparison.CODES,
			revenue.CODE,
		}
		fields = {"annual_accounts", "electronic_balance_sheet", "corporate_income_tax_return"}
		self.assertEqual(sorted((codes | fields) - names), [])

	def test_gives_the_order_of_the_work_of_a_year(self):
		self.assertEqual(
			STEP.findall(section()),
			[
				"Bücher",
				"Rückstellungen",
				"Jahresabschluss",
				"E-Bilanz",
				"Körperschaftsteuererklärung",
				"Gewerbesteuererklärung",
				"Umsatzsteuererklärung",
				"Abgabe",
			],
		)

	def test_each_link_of_the_section_leads_to_a_heading_that_exists(self):
		for target in LINK.findall(section()):
			name, _, anchor = target.partition("#")
			with self.subTest(link=target):
				linked = (DOCS / name).read_text(encoding="utf-8")
				if anchor:
					self.assertIn(anchor, anchors(linked))

	def test_the_pages_of_the_documents_link_the_section(self):
		self.assertIn("zusammenspiel-der-jahresmeldungen", anchors(PAGE.read_text(encoding="utf-8")))
		for name in PAGES:
			with self.subTest(page=name):
				self.assertIn(f"]({TARGET})", (DOCS / name).read_text(encoding="utf-8"))

	def test_the_architecture_names_the_modules_of_the_interplay(self):
		text = (DOCS / "architektur.md").read_text(encoding="utf-8")
		(row,) = (
			line
			for line in text.splitlines()
			if line.startswith("| `electronic_balance_sheet/comparison.py`")
		)
		self.assertIn("`annual_vat_return/revenue.py`", row)
		self.assertIn(f"]({TARGET})", row)
