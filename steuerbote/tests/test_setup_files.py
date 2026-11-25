"""The page Steuerbote einrichten and the Frappe layer of the setup, read from their files without a bench: who may
open the page, which method it calls, that every text reads in German and that the report escapes what the site
holds."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.setup import steps

APP = Path(__file__).resolve().parents[1]
PAGE = APP / "steuerbote" / "page" / "steuerbote_setup"
SETUP = APP / "steuerbote" / "setup.py"
TRANSLATIONS = APP / "translations" / "de.csv"
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
# Labels Frappe translates itself.
FRAMEWORK_LABELS = frozenset(
	{"Company", "Document", "Email", "Failed", "Name", "Open", "Phone", "Skipped", "Step"}
)


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def assignments(path: Path) -> dict[str, ast.expr]:
	"""The values of the module-level assignments of a file, by name, as parsed."""
	return {
		node.targets[0].id: node.value
		for node in ast.parse(path.read_text(encoding="utf-8")).body
		if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
	}


def messages(path: Path) -> set[str]:
	"""The templates the tuple MESSAGES of a module names."""
	values = assignments(path)
	return {ast.literal_eval(values[name.id]) for name in values["MESSAGES"].elts}


class SetupPageFilesTest(TestCase):
	def setUp(self):
		self.page = json.loads((PAGE / "steuerbote_setup.json").read_text(encoding="utf-8"))
		self.script = (PAGE / "steuerbote_setup.js").read_text(encoding="utf-8")
		self.source = SETUP.read_text(encoding="utf-8")

	def test_the_page_is_a_standard_page_of_the_module_for_system_and_accounts_managers(self):
		self.assertEqual(
			{key: self.page[key] for key in ("doctype", "name", "page_name", "module", "standard")},
			{
				"doctype": "Page",
				"name": "steuerbote-setup",
				"page_name": "steuerbote-setup",
				"module": "Steuerbote",
				"standard": "Yes",
			},
		)
		self.assertEqual(
			[role["role"] for role in self.page["roles"]], ["System Manager", "Accounts Manager"]
		)
		self.assertEqual(
			ast.literal_eval(assignments(SETUP)["ROLES"]), ("System Manager", "Accounts Manager")
		)
		self.assertIn('frappe.pages["steuerbote-setup"].on_page_load', self.script)

	def test_the_page_calls_the_setup_whitelisted_for_post(self):
		(method,) = re.findall(r'const SETUP_METHOD = "([\w.]+)";', self.script)
		self.assertEqual(method, "steuerbote.steuerbote.setup.set_up")
		self.assertRegex(self.source, r'@frappe\.whitelist\(methods=\["POST"\]\)\ndef set_up\(company: str\)')
		self.assertIn("frappe.only_for(ROLES, message=True)", self.source)

	def test_the_outcomes_of_the_page_are_those_of_the_core(self):
		shown = set(re.findall(r"\n\t(\w+): \{ label: __\(", self.script))
		self.assertEqual(shown, {outcome.value for outcome in steps.Outcome})

	def test_every_text_of_the_page_and_of_the_setup_reads_in_german(self):
		german = translations()
		texts = {self.page["title"]}
		texts.update(TRANSLATED_LITERAL.findall(self.script))
		texts.update(TRANSLATED_LITERAL.findall(self.source))
		values = assignments(SETUP)
		texts.update(messages(SETUP))
		texts.update(entry["label"] for entry in ast.literal_eval(values["BUILT_IN_STEPS"]))
		texts.update(label for _field, label in ast.literal_eval(values["DATENLIEFERANT_LABELS"]))
		texts.update(steps.MESSAGES)
		self.assertEqual(len(messages(SETUP)), 35)
		self.assertIn("Set Up Steuerbote", texts)
		self.assertEqual(sorted(texts - german.keys() - FRAMEWORK_LABELS), [])
		self.assertEqual(german["Set Up Steuerbote"], "Steuerbote einrichten")
		self.assertEqual(german["Set Up"], "Einrichten")

	def test_the_report_escapes_what_the_site_holds(self):
		report = re.search(
			r"\nfunction show_report\(report, result\) \{\n(?P<body>.*?)\n\}\n", self.script, re.DOTALL
		)
		self.assertIsNotNone(report)
		body = report["body"]
		self.assertIn("const escape = frappe.utils.escape_html;", body)
		for value in ("step.label", "step.key", "note.text", "step.document_label", "result.company"):
			with self.subTest(value=value):
				shown = re.findall(rf"(?:\$\{{|= )[^}};]*{re.escape(value)}[^}};]*", body)
				self.assertTrue(shown)
				self.assertTrue(all("escape" in expression for expression in shown), shown)
