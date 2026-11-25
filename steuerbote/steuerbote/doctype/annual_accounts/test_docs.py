"""docs/jahresabschluss.md describes the Annual Accounts as their files, the bridge and the core of the Jahresabschluss
hold them, and the architecture and the setup name what the package brings, read without a bench."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.hgb.disclosure import DisclosureCode
from steuerbote.hgb.notes import NoteCode
from steuerbote.hgb.statement import Code as StatementCode
from steuerbote.jahresmeldung.lifecycle import ACCOUNTS, standard_fields
from steuerbote.steuerbote.doctype.annual_accounts import bridge

APP = Path(__file__).resolve().parents[3]
DOCS = APP.parent / "docs"
PAGE = DOCS / "jahresabschluss.md"
ARCHITECTURE = DOCS / "architektur.md"
DISCLOSURE = DOCS / "offenlegung.md"
SETUP = DOCS / "einrichtung.md"
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
HOOKS = APP / "hooks.py"
DOCUMENT = "annual_accounts"
TABLES = (
	"annual_accounts_line",
	"annual_accounts_note",
	"annual_accounts_signatory",
	"annual_accounts_prior_entry",
)
LAYOUT_FIELDS = frozenset({"Section Break", "Column Break"})
FRAMEWORK_FIELDS = frozenset({"naming_series", "amended_from"})
"""The fields Frappe gives a submittable DocType with a naming series, which the page leaves to Frappe."""
RECALCULATE = "SB-NEU-BERECHNEN"
"""The code of the finding of the base that asks for Berechnen (steuerbote/steuerbote/annual_filing.py)."""
NOT_WRITTEN = frozenset(
	{NoteCode.NEGATIVE, NoteCode.NO_RATE, NoteCode.NO_CONDITIONS, DisclosureCode.BEFORE_ADOPTION}
	| {DisclosureCode.NO_SIGNATURE, DisclosureCode.CAPITAL}
)
"""The codes of the core the Annual Accounts write in no finding: entries of Haftungsverhältnisse and Vorschüsse, which
the document keeps in the texts of its Angaben, what holds an Übermittlung back, which the step refuses with a
message, and the capital of the register."""
STEPS = (
	"Preview of the Offenlegung",
	"XBRL for the Unternehmensregister",
	"Record Übermittlung",
	"Record Einstellung",
	"Post Ergebnisverwendung",
)
FRAMEWORK_GERMAN = {
	"Amount": "Betrag",
	"Channel": "Kanal",
	"Code": "Code",
	"Description": "Beschreibung",
	"Fees": "Gebühren",
	"Function": "Funktion",
	"Receipt": "Beleg",
	"Requirement": "Anforderung",
	"Source": "Quelle",
	"Text": "Text",
}
"""The labels Frappe and ERPNext translate themselves, as frappe/locale/de.po and erpnext/locale/de.po of version 16
translate them."""
LINK = re.compile(r"\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6} (.+)$", re.MULTILINE)


def documented(text: str) -> set[str]:
	"""The names a page writes as code outside its code blocks."""
	prose = re.sub(r"^```.*?^```$", "", text, flags=re.DOTALL | re.MULTILINE)
	return set(re.findall(r"`([^`]+)`", prose))


def definition(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def own_fields(name: str) -> list[dict]:
	return [
		field
		for field in definition(name)["fields"]
		if field["fieldtype"] not in LAYOUT_FIELDS and field["fieldname"] not in FRAMEWORK_FIELDS
	]


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return {**FRAMEWORK_GERMAN, **dict(csv.reader(file))}


def anchors(text: str) -> set[str]:
	"""The anchors of the headings of a page, as GitHub writes them: lower case, without punctuation, a hyphen for
	each space."""
	return {
		re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
		for heading in HEADING.findall(text)
	}


def codes() -> set[str]:
	"""The codes of the findings the Annual Accounts write: those of the bridge, of the core of the Jahresabschluss
	and of the base."""
	return {
		*(code.value for code in bridge.Code),
		*(code.value for code in StatementCode),
		*(code.value for code in NoteCode if code not in NOT_WRITTEN),
		*(code.value for code in DisclosureCode if code not in NOT_WRITTEN),
		RECALCULATE,
	}


class PageTest(TestCase):
	def setUp(self):
		self.text = PAGE.read_text(encoding="utf-8")
		self.names = documented(self.text)

	def test_names_every_field_of_the_document_and_of_its_tables(self):
		for name in (DOCUMENT, *TABLES):
			with self.subTest(doctype=name):
				fields = {field["fieldname"] for field in own_fields(name)}
				self.assertEqual(sorted(fields - self.names), [])

	def test_names_each_field_and_table_by_its_german_label(self):
		german = translations()
		standard = {item.fieldname for item in standard_fields(ACCOUNTS, "Annual Accounts", transmits=False)}
		missing = [
			f"{DOCUMENT}.{field['fieldname']}"
			for field in own_fields(DOCUMENT)
			if field["fieldname"] not in standard
			and german.get(field["label"], field["label"]) not in self.text
		]
		for child in TABLES:
			if german[definition(child)["name"]] not in self.text:
				missing.append(child)
			missing += [
				f"{child}.{field['fieldname']}"
				for field in own_fields(child)
				if field["label"] in german and german[field["label"]] not in self.text
			]
		self.assertEqual(missing, [])

	def test_names_every_code_a_finding_of_the_document_takes(self):
		self.assertIn("JA-VORJAHR-FEHLT", codes())
		self.assertIn("JA-UNTERSCHRIFT-FEHLT", codes())
		self.assertEqual(sorted(codes() - self.names), [])

	def test_names_each_step_by_its_german_label(self):
		german = translations()
		for step in STEPS:
			with self.subTest(step=step):
				self.assertIn(f"„{german[step]}“", self.text)

	def test_names_the_accounts_of_the_ergebnisverwendung_of_each_chart(self):
		numbers = {
			number for accounts in bridge.APPROPRIATION_ACCOUNTS.values() for number in vars_of(accounts)
		}
		self.assertEqual(sorted(numbers - set(re.findall(r"\b\d{4}\b", self.text))), [])

	def test_names_what_is_left_out(self):
		section = self.text.split("## Grenzen", 1)[1].split("\n## ", 1)[0]
		for point in ("Haftungsverhältnisse", "Größenmerkmale", "UG", "geändert", "E-Bilanz", "Dateien"):
			with self.subTest(point=point):
				self.assertIn(point, section)

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
			"| `annual_accounts/` mit `steuerbote/annual_accounts_sources.py` und `steuerbote/headcount.py` |",
			text,
		)
		annual = text.split("\n## Jahresmeldungen\n", 1)[1].split("\n## ", 1)[0]
		self.assertIn("\n### Jahresabschluss\n", annual)
		self.assertIn("](jahresabschluss.md)", annual)

	def test_the_page_of_the_offenlegung_names_the_document_that_exists(self):
		text = DISCLOSURE.read_text(encoding="utf-8")
		self.assertIn("](jahresabschluss.md)", text)
		self.assertNotIn("er ist in Arbeit", text)


def vars_of(accounts: bridge.AppropriationAccounts) -> tuple[str, ...]:
	return (accounts.legal_reserve, accounts.other_reserves, accounts.dividends)


class SetupPageTest(TestCase):
	def test_names_every_step_the_hooks_add(self):
		(assignment,) = (
			node
			for node in ast.parse(HOOKS.read_text(encoding="utf-8")).body
			if isinstance(node, ast.Assign)
			and [getattr(target, "id", None) for target in node.targets] == ["steuerbote_setup_steps"]
		)
		keys = [step["key"] for step in ast.literal_eval(assignment.value)]
		self.assertEqual(
			keys,
			[
				"books_start",
				"deadlines",
				"income_tax_mapping",
				"balance_sheet_mapping",
				"exchange_accounts",
				"company_default_accounts",
				"vat_id_label",
				"erpnext_germany_vat_id_check",
				"vat_id_automatic_check",
				"eric_settings",
			],
		)
		rows = [line for line in SETUP.read_text(encoding="utf-8").splitlines() if line.startswith("| ")]
		for key in keys:
			with self.subTest(step=key):
				self.assertTrue(any(f"(`{key}`, über den Hook)" in row for row in rows))
