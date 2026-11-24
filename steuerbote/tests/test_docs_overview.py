"""The pages that give the overview keep up with the app, read without a bench: the README links every page under
docs/ and the page of each annual document the app brings and shows only pictures that are there; every relative
link of the README, AGENTS.md and the pages leads to a page and a heading that exist; the pages that introduce the
annual documents, those on ERiC and the transmission to ELSTER and the architecture name each document the app brings;
the roadmap calls a package done once the app brings what it promised; AGENTS.md names every core of the app and, for
the year change, each year check and the year table of each module; and SECURITY.md names how to report a
vulnerability privately."""

import ast
import json
import re
import tomllib
from pathlib import Path
from unittest import TestCase

from steuerbote.ebilanz.defaults import REVISIONS
from steuerbote.ustva.years import YEARS

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
DOCS = ROOT / "docs"
README = ROOT / "README.md"
SECURITY = ROOT / "SECURITY.md"
AGENTS = ROOT / "AGENTS.md"
PYPROJECT = ROOT / "pyproject.toml"
ROADMAP = DOCS / "roadmap.md"
DEVELOPMENT = DOCS / "entwicklung.md"
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSMISSION = DOCTYPES / "elster_transmission" / "elster_transmission.py"
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6} (.+)$", re.MULTILINE)
CODE_BLOCK = re.compile(r"^```.*?^```$", re.DOTALL | re.MULTILINE)
PICTURE = re.compile(r'(?:src|href)="(docs/bilder/[^"]+)"')
CODE = re.compile(r"`([^`]+)`")
EXTERNAL = ("http://", "https://", "mailto:")
IN_PROGRESS = "in Arbeit"
# The annual documents, each with the page that describes it.
ANNUAL_DOCUMENTS = {
	"Annual VAT Return": "umsatzsteuererklaerung.md",
	"Electronic Balance Sheet": "ebilanz.md",
	"Corporate Income Tax Return": "ertragsteuern.md",
	"Trade Tax Return": "ertragsteuern.md",
	"Annual Accounts": "jahresabschluss.md",
}
DONE, PROVISIONAL = "erledigt", "erledigt, vorläufig"
INTERPLAY = (
	DOCTYPES / "electronic_balance_sheet" / "comparison.py",
	DOCTYPES / "annual_vat_return" / "revenue.py",
)
"""The comparisons of the interplay of the annual documents: the E-Bilanz with its Jahresabschluss and the
Umsatzsteuererklärung with the Umsatzerlöse."""
REPORT_A_VULNERABILITY = "https://github.com/encircle360-oss/steuerbote/security/advisories/new"


def read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
	"""The text under the heading up to the next heading of the same or a higher level."""
	level = heading.split(" ", 1)[0]
	start = text.index(f"\n{heading}\n")
	following = re.search(rf"^#{{1,{len(level)}}} ", text[start + len(heading) + 2 :], re.MULTILINE)
	end = start + len(heading) + 2 + following.start() if following else len(text)
	return text[start:end]


def introduction(text: str) -> str:
	"""The title of a page and the paragraphs before its first section."""
	return text.split("\n## ", 1)[0]


def item(text: str, lead: str) -> str:
	"""The item of a list that begins with the lead in bold, with the items nested in it."""
	lines = text.splitlines()
	(start,) = (index for index, line in enumerate(lines) if line.startswith(f"- **{lead}"))
	end = next(
		(index for index in range(start + 1, len(lines)) if not lines[index].startswith(" ")), len(lines)
	)
	return "\n".join(lines[start:end])


def anchors(text: str) -> set[str]:
	"""The anchors of the headings of a page, as GitHub writes them: lower case, without punctuation, a hyphen for
	each space."""
	return {
		re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
		for heading in HEADING.findall(CODE_BLOCK.sub("", text))
	}


def brought(doctype: str) -> bool:
	return (DOCTYPES / doctype.lower().replace(" ", "_")).is_dir()


def links(doctype: str) -> dict[str, str]:
	"""The link fields of a DocType the app brings, each with the DocType it links to."""
	name = doctype.lower().replace(" ", "_")
	definition = json.loads(read(DOCTYPES / name / f"{name}.json"))
	return {
		field["fieldname"]: field["options"] for field in definition["fields"] if field["fieldtype"] == "Link"
	}


def annual_documents() -> dict[str, str]:
	"""The annual documents the app brings, each with its page."""
	return {doctype: page for doctype, page in ANNUAL_DOCUMENTS.items() if brought(doctype)}


def transmitted() -> list[str]:
	"""The DocTypes an ELSTER Transmission names (DOCUMENT_TYPES), read from its source without Frappe."""
	(assignment,) = (
		node
		for node in ast.parse(read(TRANSMISSION)).body
		if isinstance(node, ast.Assign)
		and [getattr(target, "id", None) for target in node.targets] == ["DOCUMENT_TYPES"]
	)
	return [element.value for element in assignment.value.elts]


def cores() -> list[str]:
	"""The packages pytest collects whole, the cores of the app (testpaths in pyproject.toml)."""
	testpaths = tomllib.loads(read(PYPROJECT))["tool"]["pytest"]["ini_options"]["testpaths"]
	return [Path(path).name for path in testpaths if (ROOT / path).is_dir()]


def year_tables() -> list[str]:
	"""The modules that hold the years of each module, as the table of docs/entwicklung.md, „Jahreswechsel“, names
	them in its column Jahrestabelle, each without the package of the app in front."""
	table = section(read(DEVELOPMENT), "## Jahreswechsel").split("\n### ", 1)[0]
	rows = [line.strip().strip("|").split(" | ") for line in table.splitlines() if line.startswith("| ")]
	return [
		name.removeprefix("steuerbote/")
		for row in rows[1:]
		for name in CODE.findall(row[1])
		if name.endswith(".py")
	]


def roadmap_stand() -> dict[str, str]:
	"""The state of each package of the table of the Stufe 3."""
	rows = [
		[cell.strip() for cell in line.strip().strip("|").split(" | ")]
		for line in section(read(ROADMAP), "## Stufe 3: Jahresmeldungen").splitlines()
		if line.startswith("| ")
	]
	return {row[0]: row[-1] for row in rows[1:]}


class ReadmeTest(TestCase):
	def setUp(self):
		self.text = read(README)

	def test_the_documentation_links_every_page_under_docs(self):
		listed = set(re.findall(r"\]\(docs/([\w-]+\.md)\)", section(self.text, "## Dokumentation")))
		self.assertEqual(sorted({page.name for page in DOCS.glob("*.md")} - listed), [])

	def test_what_steuerbote_does_links_the_page_of_each_annual_document_the_app_brings(self):
		features = section(self.text, "## Was Steuerbote macht")
		self.assertTrue(annual_documents())
		for doctype, page in annual_documents().items():
			with self.subTest(doctype=doctype):
				self.assertIn(f"](docs/{page})", features)

	def test_shows_pictures_that_are_there(self):
		shown = PICTURE.findall(self.text)
		self.assertTrue(shown)
		for picture in shown:
			with self.subTest(picture=picture):
				self.assertTrue((ROOT / picture).is_file())


class LinksTest(TestCase):
	def test_each_relative_link_leads_to_a_page_and_a_heading_that_exist(self):
		for page in (README, SECURITY, ROOT / "CONTRIBUTING.md", AGENTS, *sorted(DOCS.glob("*.md"))):
			for target in LINK.findall(CODE_BLOCK.sub("", read(page))):
				if target.startswith(EXTERNAL):
					continue
				path, _, anchor = target.partition("#")
				linked = page.parent / path if path else page
				with self.subTest(page=page.name, link=target):
					self.assertTrue(linked.exists())
					if anchor and linked.suffix == ".md":
						self.assertIn(anchor, anchors(read(linked)))


class AnnualDocumentsTest(TestCase):
	def test_the_page_of_the_jahresmeldungen_names_each_document_the_app_brings_with_its_page(self):
		text = read(DOCS / "jahresmeldungen.md")
		for doctype, page in annual_documents().items():
			with self.subTest(doctype=doctype):
				self.assertIn(f"`{doctype}`", introduction(text))
				self.assertIn(f"]({page})", introduction(text))
		self.assertNotIn(IN_PROGRESS, introduction(text))
		self.assertNotIn(IN_PROGRESS, section(text, "## Grenzen"))

	def test_the_architecture_links_the_page_of_each_annual_document_the_app_brings(self):
		annual = section(read(DOCS / "architektur.md"), "## Jahresmeldungen").split("\n### ", 1)[0]
		for doctype, page in annual_documents().items():
			with self.subTest(doctype=doctype):
				self.assertIn(f"]({page})", annual)
		self.assertNotIn(IN_PROGRESS, annual)

	def test_the_pages_on_elster_link_the_page_of_each_annual_document_that_goes_over_eric(self):
		documents = {
			doctype: page for doctype, page in annual_documents().items() if doctype in transmitted()
		}
		self.assertIn("Electronic Balance Sheet", documents)
		for name in ("eric.md", "uebermittlung.md"):
			text = read(DOCS / name)
			for doctype, page in documents.items():
				with self.subTest(page=name, doctype=doctype):
					self.assertIn(f"]({page})", introduction(text))
			with self.subTest(page=name):
				self.assertNotIn(IN_PROGRESS, text)


class RoadmapTest(TestCase):
	def setUp(self):
		self.stand = roadmap_stand()

	def test_a_document_is_done_once_the_app_brings_its_doctype(self):
		for package, doctype in (
			("E-Bilanz als Beleg", "Electronic Balance Sheet"),
			("Jahresabschluss als Beleg", "Annual Accounts"),
		):
			with self.subTest(package=package):
				self.assertEqual(self.stand[package] == DONE, brought(doctype))

	def test_the_defaults_of_the_bilanzzuordnung_are_done_once_they_have_rows(self):
		"""Revision 0 of the defaults is the empty table (steuerbote/ebilanz/defaults.py)."""
		self.assertEqual(
			self.stand["Vorgaben der Bilanzzuordnung für SKR03 und SKR04"] == DONE, REVISIONS["6.9"] > 0
		)

	def test_the_year_2027_is_provisional_as_long_as_its_forms_are(self):
		self.assertEqual(self.stand["Jahrgang 2027"], PROVISIONAL if YEARS[2027].provisional else DONE)

	def test_the_integration_is_done_once_the_documents_name_and_compare_each_other(self):
		"""The Körperschaftsteuererklärung names its E-Bilanz, the E-Bilanz its Jahresabschluss, and both comparisons
		are there (docs/jahresmeldungen.md, „Zusammenspiel der Jahresmeldungen“)."""
		brings = (
			links("Corporate Income Tax Return").get("electronic_balance_sheet") == "Electronic Balance Sheet"
			and links("Electronic Balance Sheet").get("annual_accounts") == "Annual Accounts"
			and all(path.is_file() for path in INTERPLAY)
		)
		self.assertEqual(self.stand["Integration"] == DONE, brings)


class AgentsTest(TestCase):
	"""AGENTS.md is the first page a coding agent reads: where the code is and what a new year changes."""

	def setUp(self):
		self.text = read(AGENTS)

	def test_the_structure_names_every_core_of_the_app(self):
		structure = item(self.text, "Struktur")
		self.assertTrue(cores())
		for core in cores():
			with self.subTest(core=core):
				self.assertRegex(structure, rf"`(steuerbote/)?{core}`")

	def test_the_year_change_names_the_year_check_of_each_core_that_has_one(self):
		year_change = item(self.text, "Jahreswechsel")
		checks = sorted(path.parent.name for path in APP.glob("*/yearcheck.py"))
		self.assertTrue(checks)
		for core in checks:
			with self.subTest(core=core):
				self.assertIn(f"python -m steuerbote.{core}.yearcheck", year_change)

	def test_the_year_change_names_the_year_table_of_each_module(self):
		year_change = item(self.text, "Jahreswechsel")
		self.assertTrue(year_tables())
		for table in year_tables():
			with self.subTest(table=table):
				self.assertIn(f"{table}`", year_change)


class SecurityTest(TestCase):
	def test_names_the_private_reporting_of_github_and_the_address(self):
		text = read(SECURITY)
		self.assertIn(f"]({REPORT_A_VULNERABILITY})", text)
		self.assertIn("oss@encircle360.com", text)
		self.assertNotIn("sobald das Repository öffentlich ist", text)
