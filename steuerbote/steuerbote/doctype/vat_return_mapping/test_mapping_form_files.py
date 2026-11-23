"""The form of the VAT Return Mapping, read from its files without a bench: the methods it calls are whitelisted
for POST, „Steuervorlagen prüfen“ reads in German, and its dialog escapes what the site holds."""

import csv
import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[3]
FOLDER = APP / "steuerbote" / "doctype" / "vat_return_mapping"
TRANSLATIONS = APP / "translations" / "de.csv"


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


class MappingFormFilesTest(TestCase):
	def setUp(self):
		self.script = (FOLDER / "vat_return_mapping.js").read_text(encoding="utf-8")
		self.source = (FOLDER / "vat_return_mapping.py").read_text(encoding="utf-8")

	def test_the_methods_the_form_calls_are_whitelisted_for_post(self):
		methods = sorted(set(re.findall(r'frm\.call\("(\w+)"', self.script)))
		self.assertEqual(methods, ["check_tax_templates", "load_defaults", "watch_template_accounts"])
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
