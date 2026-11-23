"""The provisional forms of a year at the VAT Return, read from its files without a bench: the field that says so, its
German texts and those of the messages of the controller, and the mark on the print format „Umsatzsteuer-Voranmeldung“
(steuerbote/ustva/years.py)."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[3]
FOLDER = APP / "steuerbote" / "doctype" / "vat_return"
TRANSLATIONS = APP / "translations" / "de.csv"
PRINT_FORMAT = (
	APP / "steuerbote" / "print_format" / "umsatzsteuer_voranmeldung" / "umsatzsteuer_voranmeldung.html"
)
TRANSLATED_LITERAL = re.compile(r'\b_{1,2}\(\s*"((?:[^"\\]|\\.)*)"')


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


class FieldTest(TestCase):
	def setUp(self):
		self.definition = json.loads((FOLDER / "vat_return.json").read_text(encoding="utf-8"))
		self.field = next(field for field in self.definition["fields"] if field["fieldname"] == "provisional")

	def test_is_a_read_only_check_after_ready(self):
		self.assertEqual(
			{key: self.field.get(key) for key in ("fieldtype", "label", "read_only", "default")},
			{"fieldtype": "Check", "label": "Provisional Forms", "read_only": 1, "default": "0"},
		)
		order = self.definition["field_order"]
		self.assertEqual(order.index("provisional"), order.index("ready") + 1)

	def test_its_texts_and_the_messages_of_the_provisional_forms_read_in_german(self):
		german = translations()
		self.assertEqual(german[self.field["label"]], "Vorläufige Vordrucke")
		self.assertIn("vorläufig", german[self.field["description"]])
		controller = (FOLDER / "vat_return.py").read_text(encoding="utf-8")
		messages = [text for text in TRANSLATED_LITERAL.findall(controller) if "provisionally" in text]
		self.assertTrue(messages)
		for message in messages:
			with self.subTest(message=message):
				self.assertIn("vorläufig", german[message])


class PrintFormatTest(TestCase):
	def test_marks_the_forms_of_a_provisional_year_under_the_title(self):
		template = PRINT_FORMAT.read_text(encoding="utf-8")
		self.assertIn("{%- set provisional = doc.provisional_forms() %}", template)
		self.assertIn(
			'<p class="sb-subtitle">vorläufig ({{ provisional.documentation }}, Vordruck {{ provisional.form_year }})</p>',
			template,
		)
		self.assertLess(template.index("<h1>"), template.index("vorläufig ("))
