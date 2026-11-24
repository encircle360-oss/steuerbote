"""docs/ebilanz.md describes the E-Bilanz as its files, the bridge and the core hold it, and docs/taxonomie.md the
HGB-Taxonomie as steuerbote/xbrl holds it, read without a bench."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.jahresmeldung.lifecycle import FILING, standard_fields
from steuerbote.steuerbote.doctype.electronic_balance_sheet import bridge
from steuerbote.ustjahr import years
from steuerbote.xbrl import mapping, profiles
from steuerbote.xbrl.taxonomy import View
from steuerbote.xbrl.versions import TAXONOMIES

APP = Path(__file__).resolve().parents[3]
DOCS = APP.parent / "docs"
PAGE = DOCS / "ebilanz.md"
TAXONOMY_PAGE = DOCS / "taxonomie.md"
ARCHITECTURE = DOCS / "architektur.md"
DOCTYPES = APP / "steuerbote" / "doctype"
CORE = APP / "ebilanz"
TRANSLATIONS = APP / "translations" / "de.csv"
DOCTYPE = "electronic_balance_sheet"
CHILDREN = (
	"electronic_balance_sheet_position",
	"electronic_balance_sheet_account",
	"electronic_balance_sheet_fixed_asset",
	"electronic_balance_sheet_transfer",
)
LAYOUT_FIELDS = frozenset({"Section Break", "Column Break"})
FRAMEWORK_FIELDS = frozenset({"naming_series", "amended_from"})
"""The fields Frappe gives a submittable DocType with a naming series, which the page leaves to Frappe."""
RECALCULATE = "SB-NEU-BERECHNEN"
"""The code of the finding of the base that asks for Berechnen (steuerbote/steuerbote/annual_filing.py)."""
CORE_CODE = re.compile(r'"(EB-[A-Z0-9-]+)"')
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6} (.+)$", re.MULTILINE)


def documented(text: str) -> set[str]:
	"""The names a page writes as code outside its code blocks, which a list may indent."""
	prose = re.sub(r"^[ \t]*```.*?^[ \t]*```$", "", text, flags=re.DOTALL | re.MULTILINE)
	return set(re.findall(r"`([^`]+)`", prose))


def definition(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def own_fields(name: str) -> list[dict]:
	"""The fields of a DocType the page names: those that are no layout and that Frappe does not give it."""
	return [
		field
		for field in definition(name)["fields"]
		if field["fieldtype"] not in LAYOUT_FIELDS and field["fieldname"] not in FRAMEWORK_FIELDS
	]


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def anchors(text: str) -> set[str]:
	"""The anchors of the headings of a page, as GitHub writes them: lower case, without punctuation, a hyphen for
	each space."""
	return {
		re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
		for heading in HEADING.findall(text)
	}


def codes() -> set[str]:
	"""The codes of the findings of the E-Bilanz: those of Steuerbote, of the Bilanzzuordnung, of the core and of the
	base."""
	core = {
		code for path in CORE.glob("*.py") for code in CORE_CODE.findall(path.read_text(encoding="utf-8"))
	}
	return {*bridge.CODES, *(code.value for code in mapping.Code), *core, RECALCULATE}


class LinksTest(TestCase):
	def test_each_link_leads_to_a_page_and_a_heading_that_exist(self):
		for page in (PAGE, TAXONOMY_PAGE):
			text = page.read_text(encoding="utf-8")
			for target in LINK.findall(text):
				if target.startswith(("http://", "https://")):
					continue
				name, _, anchor = target.partition("#")
				linked = (DOCS / name).read_text(encoding="utf-8") if name else text
				with self.subTest(page=page.name, link=target):
					if anchor:
						self.assertIn(anchor, anchors(linked))


class PageTest(TestCase):
	def setUp(self):
		self.text = PAGE.read_text(encoding="utf-8")
		self.names = documented(self.text)

	def test_names_every_field_of_the_e_bilanz_and_of_its_tables(self):
		for name in (DOCTYPE, *CHILDREN):
			with self.subTest(doctype=name):
				self.assertEqual(sorted({field["fieldname"] for field in own_fields(name)} - self.names), [])

	def test_names_each_field_and_table_by_its_german_label(self):
		"""The E-Bilanz by every label of its own fields, as de.csv translates them or as they read in German already;
		its tables by their name and every label that de.csv translates, the others being Frappe's."""
		german = translations()
		standard = {
			item.fieldname for item in standard_fields(FILING, definition(DOCTYPE)["name"], transmits=True)
		}
		missing = [
			f"{DOCTYPE}.{field['fieldname']}"
			for field in own_fields(DOCTYPE)
			if field["fieldname"] not in standard
			and german.get(field["label"], field["label"]) not in self.text
		]
		for child in CHILDREN:
			if german[definition(child)["name"]] not in self.text:
				missing.append(child)
			missing += [
				f"{child}.{field['fieldname']}"
				for field in own_fields(child)
				if field["label"] in german and german[field["label"]] not in self.text
			]
		self.assertEqual(missing, [])

	def test_names_every_code_a_finding_of_the_e_bilanz_takes(self):
		self.assertIn("EB-KORREKTUR-SUMME", codes())
		self.assertIn("BILANZ-OHNE-PLATZ", codes())
		self.assertIn(bridge.TWO_SCHEDULES, codes())
		self.assertEqual(sorted(codes() - self.names), [])

	def test_names_the_options_of_its_selects(self):
		for value in (
			*bridge.STATEMENT_TYPES,
			*bridge.VALUE_TYPES,
			*bridge.TRANSFER_KINDS,
			"HAOE",
			"HGBM",
			"AO",
		):
			with self.subTest(option=value):
				self.assertIn(value, self.text)

	def test_names_the_deadlines_of_2026(self):
		"""FAQ zur E-Bilanz, Tz. 5: the E-Bilanz goes with the Körperschaftsteuererklärung."""
		for advisor in (False, True):
			with self.subTest(advisor=advisor):
				self.assertIn(f"{years.filing_deadline(2026, advisor):%d.%m.%Y}", self.text)

	def test_says_that_mein_elster_takes_no_e_bilanz(self):
		self.assertIn("Mein ELSTER nimmt keine E-Bilanz an", self.text)
		self.assertIn("„XBRL exportieren“", self.text)
		self.assertIn("„Als außerhalb abgegeben vermerken“", self.text)

	def test_names_where_the_koerperschaftsteuererklaerung_takes_its_figures(self):
		section = self.text.split("## Für die Körperschaftsteuererklärung", 1)[1].split("\n## ", 1)[0]
		for name in ("net_income", "tax_net_income", "tax_equity", "bs.eqLiab.equity.subscribed"):
			with self.subTest(name=name):
				self.assertIn(f"`{name}`", section)

	def test_the_architecture_names_the_module_and_links_the_pages(self):
		text = ARCHITECTURE.read_text(encoding="utf-8")
		self.assertIn("| `electronic_balance_sheet/` mit `steuerbote/ebilanz_sources.py` |", text)
		self.assertNotIn("\n## E-Bilanz\n", text)
		jahresmeldungen = text.split("\n## Jahresmeldungen\n", 1)[1].split("\n## ", 1)[0]
		self.assertIn("\n### E-Bilanz\n", jahresmeldungen)
		self.assertIn("](ebilanz.md)", text)
		self.assertIn("](taxonomie.md)", text)


class TaxonomyPageTest(TestCase):
	def setUp(self):
		self.text = TAXONOMY_PAGE.read_text(encoding="utf-8")
		self.names = documented(self.text)

	def test_names_each_version_with_its_package_and_checksum(self):
		for version in TAXONOMIES.values():
			with self.subTest(version=version.version):
				self.assertIn(f"| {version.version} |", self.text)
				self.assertIn(version.archive_url, self.text)
				self.assertIn(version.archive_url.rsplit("/", 1)[1], self.names)
				self.assertIn(version.archive_sha256, self.names)
				self.assertIn(f"{version.letter_date:%d.%m.%Y}", self.text)
				self.assertIn(f"{version.real_cases_from:%d.%m.%Y}", self.text)

	def test_says_how_the_operator_installs_the_taxonomy(self):
		for version in TAXONOMIES.values():
			for key in (version.config_key, version.config_sha256_key):
				with self.subTest(key=key):
					self.assertIn(f"bench set-config -g {key} ", self.text)
		for name in (
			"steuerbote_taxonomy_root",
			"sites/taxonomy",
			"steuerbote-taxonomy.json",
			"taxonomy_6_9",
		):
			with self.subTest(name=name):
				self.assertIn(name, self.names)
		self.assertIn("„Taxonomie einrichten“", self.text)
		self.assertIn("„Laufzeitumgebung prüfen“", self.text)

	def test_names_the_views_and_the_profiles(self):
		for view in View:
			with self.subTest(view=view):
				self.assertIn(view.value, self.names)
		for profile in profiles.PROFILES:
			with self.subTest(profile=profile.name):
				self.assertIn(profile.name.upper(), self.names)

	def test_says_that_6_10_joins_6_9(self):
		"""The version of the fiscal years from 2027, which the field „HGB-Taxonomie“ offers beside 6.9 and „Auf neue
		Taxonomie heben“ brings to the Bilanzzuordnung."""
		self.assertIn("6.10", TAXONOMIES)
		self.assertIn("Die Version 6.10", self.text)
		self.assertIn("„Auf neue Taxonomie heben“", self.text)
