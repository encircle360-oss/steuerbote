"""docs/ertragsteuern.md describes the Corporate Income Tax Return and the Trade Tax Return as their files, the
bridges and the cores hold them, read without a bench."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.gewst import chain as gewst_chain
from steuerbote.jahresmeldung.lifecycle import FILING, standard_fields
from steuerbote.kst import chain as kst_chain
from steuerbote.kst import einlagekonto, provisions
from steuerbote.kst.years import year_of
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge
from steuerbote.steuerbote.doctype.trade_tax_return import bridge as trade_tax_bridge
from steuerbote.ustjahr import years

APP = Path(__file__).resolve().parents[3]
DOCS = APP.parent / "docs"
PAGE = DOCS / "ertragsteuern.md"
ARCHITECTURE = DOCS / "architektur.md"
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
RETURNS = {
	"corporate_income_tax_return": (
		"corporate_income_tax_return_line",
		"corporate_income_tax_return_holding_result",
		"corporate_income_tax_return_credit",
		"corporate_income_tax_return_donation",
		"corporate_income_tax_return_distribution",
		"corporate_income_tax_return_contribution",
	),
	"trade_tax_return": (
		"trade_tax_return_line",
		"trade_tax_return_municipality",
		"trade_tax_return_holding",
	),
}
LAYOUT_FIELDS = frozenset({"Section Break", "Column Break"})
FRAMEWORK_FIELDS = frozenset({"naming_series", "amended_from"})
"""The fields Frappe gives a submittable DocType with a naming series, which the page leaves to Frappe."""
RECALCULATE = "SB-NEU-BERECHNEN"
"""The code of the finding of the base that asks for Berechnen (steuerbote/steuerbote/annual_filing.py)."""
TABLE_OPTIONS = (
	("corporate_income_tax_return_holding_result", "kind"),
	("corporate_income_tax_return_distribution", "kind"),
	("corporate_income_tax_return_contribution", "treatment"),
)
"""The options of the tables that the page lists in a table of their own, each in a row."""
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6} (.+)$", re.MULTILINE)
REVIEW = "## Prüfliste für die Steuerberatung"
REVIEW_POINTS = 6
"""The points of the review list of the research of stage 3 for the Steuerberatung (KSt note 5.5)."""


def documented(text: str) -> set[str]:
	"""The names a page writes as code outside its code blocks."""
	prose = re.sub(r"^```.*?^```$", "", text, flags=re.DOTALL | re.MULTILINE)
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


def fields_of(name: str) -> set[str]:
	return {field["fieldname"] for field in own_fields(name)}


def options_of(name: str, fieldname: str) -> list[str]:
	(field,) = (field for field in definition(name)["fields"] if field["fieldname"] == fieldname)
	return [option for option in field["options"].split("\n") if option]


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
	"""The codes of the findings of both returns: those of the bridges, of the cores and of the base."""
	return {
		*bridge.CODES,
		*trade_tax_bridge.CODES,
		*(code.value for code in kst_chain.Code),
		*(code.value for code in einlagekonto.Code),
		*(code.value for code in gewst_chain.Code),
		RECALCULATE,
	}


class PageTest(TestCase):
	def setUp(self):
		self.text = PAGE.read_text(encoding="utf-8")
		self.names = documented(self.text)

	def test_names_every_field_of_both_returns_and_of_their_tables(self):
		for parent, children in RETURNS.items():
			for name in (parent, *children):
				with self.subTest(doctype=name):
					self.assertEqual(sorted(fields_of(name) - self.names), [])

	def test_names_each_field_and_table_by_its_german_label(self):
		"""The returns by every label of their own fields, as de.csv translates them or as they read in German already;
		their tables by their name and every label that de.csv translates, the others being Frappe's."""
		german = translations()
		missing = []
		for parent, children in RETURNS.items():
			standard = {
				item.fieldname for item in standard_fields(FILING, definition(parent)["name"], transmits=True)
			}
			for field in own_fields(parent):
				if (
					field["fieldname"] not in standard
					and german.get(field["label"], field["label"]) not in self.text
				):
					missing.append(f"{parent}.{field['fieldname']}")
			for child in children:
				if german[definition(child)["name"]] not in self.text:
					missing.append(child)
				for field in own_fields(child):
					if field["label"] in german and german[field["label"]] not in self.text:
						missing.append(f"{child}.{field['fieldname']}")
		self.assertEqual(missing, [])

	def test_names_every_code_a_finding_of_the_returns_takes(self):
		self.assertIn(bridge.PROVISIONAL, codes())
		self.assertIn("GEWST-HEBESATZ-FEHLT", codes())
		self.assertEqual(sorted(codes() - self.names), [])

	def test_names_each_line_that_takes_a_correction(self):
		self.assertEqual(sorted(set(bridge.CORRECTABLE_FIELDS) - self.names), [])

	def test_names_the_deadlines_of_2026(self):
		for advisor in (False, True):
			with self.subTest(advisor=advisor):
				self.assertIn(f"{years.filing_deadline(2026, advisor):%d.%m.%Y}", self.text)

	def test_names_the_accounts_of_the_taxes_their_provisions_and_refunds_of_each_chart(self):
		numbers = {
			number
			for accounts in provisions.ACCOUNTS.values()
			for taxed in (accounts.kst, accounts.solz, accounts.gewst)
			for number in (taxed.expense, taxed.provision, taxed.refund)
		}
		named = set(re.findall(r"\b\d{4}\b", self.text))
		self.assertEqual(sorted(numbers - named), [])

	def test_names_the_provisional_forms_of_2026_as_the_print_marks_them(self):
		year = year_of(2026)
		self.assertTrue(year.provisional)
		self.assertIn(f"„vorläufig (Jahresdokumentation {year.documentation_year})“", self.text)

	def test_says_that_mein_elster_imports_neither_return(self):
		self.assertIn(
			"Mein ELSTER importiert keine Körperschaftsteuererklärung und keine Gewerbesteuererklärung",
			self.text,
		)

	def test_names_each_option_of_the_tables_as_the_form_shows_it(self):
		german = translations()
		rows = set(re.findall(r"^\| ([^|]+?) \|", self.text, re.MULTILINE))
		missing = [
			option
			for name, fieldname in TABLE_OPTIONS
			for option in options_of(name, fieldname)
			if german.get(option, option) not in rows
		]
		missing += [
			option
			for option in options_of("corporate_income_tax_return_contribution", "kind")
			if german.get(option, option) not in self.text
		]
		self.assertEqual(missing, [])

	def test_lists_the_review_for_the_steuerberatung(self):
		section = self.text.split(REVIEW, 1)[1].split("\n## ", 1)[0]
		self.assertEqual(len(re.findall(r"^\d+\. \*\*", section, re.MULTILINE)), REVIEW_POINTS)

	def test_each_link_leads_to_a_page_and_a_heading_that_exist(self):
		for target in LINK.findall(self.text):
			if target.startswith(("http://", "https://")):
				continue
			page, _, anchor = target.partition("#")
			text = (DOCS / page).read_text(encoding="utf-8") if page else self.text
			with self.subTest(link=target):
				if anchor:
					self.assertIn(anchor, anchors(text))

	def test_the_architecture_names_the_modules_and_links_the_page(self):
		text = ARCHITECTURE.read_text(encoding="utf-8")
		self.assertIn(
			"| `corporate_income_tax_return/` und `trade_tax_return/` mit `steuerbote/income_tax_sources.py` |",
			text,
		)
		self.assertIn("## Erklärungen der Ertragsteuern", text)
		self.assertIn("](ertragsteuern.md)", text)
