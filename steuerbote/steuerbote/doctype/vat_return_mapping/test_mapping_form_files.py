"""The form of the VAT Return Mapping, read from its files without a bench: the methods it calls are whitelisted
for POST, „Steuervorlagen prüfen“ and „Vorgaben aktualisieren“ read in German, and their dialogs escape what the site
holds."""

import ast
import csv
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.mapping_sync import CHECK_FIELDS, RULE_FIELDS
from steuerbote.mappings.diff import Change, Origin

APP = Path(__file__).resolve().parents[3]
FOLDER = APP / "steuerbote" / "doctype" / "vat_return_mapping"
TRANSLATIONS = APP / "translations" / "de.csv"
DIFFERENCES_SCRIPT = APP / "public" / "js" / "mapping_differences.js"
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


class MappingFormFilesTest(TestCase):
	def setUp(self):
		self.script = (FOLDER / "vat_return_mapping.js").read_text(encoding="utf-8")
		self.source = (FOLDER / "vat_return_mapping.py").read_text(encoding="utf-8")

	def test_the_methods_the_form_calls_are_whitelisted_for_post(self):
		methods = sorted(set(re.findall(r'frm\.call\("(\w+)"', self.script)))
		self.assertEqual(
			methods,
			[
				"check_tax_templates",
				"compare_with_defaults",
				"load_defaults",
				"update_from_defaults",
				"watch_template_accounts",
			],
		)
		for method in methods:
			with self.subTest(method=method):
				self.assertRegex(self.source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')

	def test_the_check_reads_in_german(self):
		german = translations()
		self.assertEqual(german["Check Tax Templates"], "Steuervorlagen prüfen")
		self.assertEqual(german["Watch at the Level Blocking"], "Auf der Stufe „Sperrt“ beobachten")

	def test_the_dialog_escapes_numbers_names_and_templates_of_the_accounts(self):
		dialog = re.search(
			r"\nfunction show_template_accounts\(frm, accounts\) \{\n(?P<body>.*?)\n\}\n",
			self.script,
			re.DOTALL,
		)
		self.assertIsNotNone(dialog)
		body = dialog["body"]
		self.assertIn("const escape = frappe.utils.escape_html;", body)
		for value in ("account.account_number", "account.account_name", "account.templates"):
			with self.subTest(value=value):
				shown = re.findall(rf"\$\{{[^}}]*{re.escape(value)}[^}}]*\}}", body)
				self.assertTrue(shown)
				self.assertTrue(all("escape" in expression for expression in shown), shown)


def labels_of(source: str, name: str) -> dict[str, str]:
	"""A module-level dict of the source, keyed by the name of an enum member or by its text."""
	for node in ast.parse(source).body:
		if isinstance(node, ast.Assign) and [target.id for target in node.targets] == [name]:
			return {
				key.attr if isinstance(key, ast.Attribute) else key.value: value.value
				for key, value in zip(node.value.keys, node.value.values, strict=True)
			}
	raise AssertionError(f"{name} not found")


class DifferencesFilesTest(TestCase):
	"""Vorgaben aktualisieren and the dialog of the differences it shares with Zuordnung importieren."""

	def setUp(self):
		self.source = (FOLDER / "vat_return_mapping.py").read_text(encoding="utf-8")
		self.dialog = DIFFERENCES_SCRIPT.read_text(encoding="utf-8")
		self.script = (FOLDER / "vat_return_mapping.js").read_text(encoding="utf-8")

	def test_the_form_includes_the_dialog_of_the_differences(self):
		self.assertTrue(
			self.script.startswith('{% include "steuerbote/public/js/mapping_differences.js" %}\n')
		)

	def test_the_dialog_reads_in_german(self):
		german = translations()
		texts = set(TRANSLATED_LITERAL.findall(self.dialog))
		self.assertIn("Account or Tax Check", texts)
		self.assertEqual(sorted(texts - german.keys()), [])
		self.assertEqual(german["Update Defaults"], "Vorgaben aktualisieren")

	def test_every_change_origin_and_field_has_a_german_label(self):
		german = translations()
		changes = labels_of(self.source, "CHANGES")
		origins = labels_of(self.source, "ORIGINS")
		fields = labels_of(self.source, "FIELD_LABELS")
		self.assertEqual(set(changes), {change.name for change in Change})
		self.assertEqual(set(origins), {origin.name for origin in Origin})
		self.assertEqual(set(fields), {"place", "level", *RULE_FIELDS, *CHECK_FIELDS})
		labels = {*changes.values(), *origins.values(), *fields.values()}
		self.assertEqual(sorted(labels - german.keys()), [])

	def test_the_dialog_escapes_every_text_of_the_server(self):
		rows = re.search(r"const rows = differences\.map\((?P<body>.*?)\n\t\);\n", self.dialog, re.DOTALL)
		self.assertIsNotNone(rows)
		body = rows["body"]
		for value in ("id", "subject", "change", "fields", "current", "proposed", "origin"):
			with self.subTest(value=value):
				shown = re.findall(rf"\$\{{[^}}]*difference\.{value}\b[^}}]*\}}", body)
				self.assertTrue(shown)
				self.assertTrue(
					all("escape" in expression or expression.endswith("? `") for expression in shown), shown
				)
		self.assertIn("${escape(intro)}", self.dialog)
		self.assertIn("${escape(proposed_label)}", self.dialog)
