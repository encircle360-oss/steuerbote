"""The tables of the Vorperiodenvergleich and the hints, read from their files without a bench: every text
has a German translation in translations/de.csv, and the form shows what the tables do not know as blank."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[3]
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
SCRIPT = DOCTYPES / "vat_return" / "vat_return.js"
TABLES = ("vat_return_comparison", "vat_return_hint")
VAT_RETURN_FIELDS = ("hints_section", "hints", "comparison_section", "comparison")
# The severities of a hint are German already, like the status of a return.
UNTRANSLATED = frozenset({"Hinweis", "Warnung"})
# Labels Frappe and ERPNext translate themselves; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{"Code", "Description", "Kind", "Message", "Party", "Voucher No", "Voucher Type"}
)


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def doctype(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def fields(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in doctype(name)["fields"]}


def field_texts(definitions) -> set[str]:
	texts = set()
	for field in definitions:
		texts.update(field[key] for key in ("label", "description") if field.get(key))
		if field["fieldtype"] == "Select":
			texts.update(option for option in field["options"].split("\n") if option)
	return texts


class TranslationsTest(TestCase):
	def test_every_text_of_the_tables_and_their_sections_is_translated(self):
		texts = set()
		for name in TABLES:
			definition = doctype(name)
			texts.update({definition["name"], definition["description"]})
			texts.update(field_texts(definition["fields"]))
		texts.update(field_texts(fields("vat_return")[name] for name in VAT_RETURN_FIELDS))
		self.assertIn("Previous Period Comparison", texts)
		self.assertEqual(sorted(texts - set(translations()) - UNTRANSLATED - FRAMEWORK_LABELS), [])

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & set(translations())), [])

	def test_the_thresholds_carry_their_german_labels(self):
		german = translations()
		settings = fields("vat_return_settings")
		self.assertEqual(
			[
				german[settings[name]["label"]]
				for name in ("comparison_threshold_percent", "comparison_threshold_amount")
			],
			["Schwelle Vorperiodenvergleich (%)", "Schwelle Vorperiodenvergleich (EUR)"],
		)


class FormTest(TestCase):
	def setUp(self):
		self.script = SCRIPT.read_text(encoding="utf-8")

	def test_the_sections_appear_with_their_rows(self):
		vat_return = fields("vat_return")
		self.assertEqual(
			{name: vat_return[f"{name}_section"]["depends_on"] for name in ("hints", "comparison")},
			{"hints": "eval:(doc.hints || []).length", "comparison": "eval:(doc.comparison || []).length"},
		)
		self.assertEqual(
			(vat_return["hints"]["options"], vat_return["comparison"]["options"]),
			("VAT Return Hint", "VAT Return Comparison"),
		)
		self.assertTrue(vat_return["hints"]["read_only"] and vat_return["comparison"]["read_only"])

	def test_the_form_leaves_what_the_comparison_does_not_know_blank(self):
		setup = re.search(r"\n\tsetup\(frm\) \{\n(?P<body>.*?)\n\t\},\n", self.script, re.DOTALL)
		self.assertIsNotNone(setup)
		self.assertIn("leave_unknown_comparison_values_blank();", setup["body"])
		self.assertIn('frappe.meta.set_formatter("VAT Return Comparison", fieldname, null,', self.script)
		known_with = re.search(r"const known_with = \{(?P<pairs>[^}]*)\}", self.script)
		self.assertIsNotNone(known_with)
		pairs = dict(re.findall(r'(\w+): "(\w+)"', known_with["pairs"]))
		self.assertEqual(
			pairs,
			{
				"previous_period": "previous_period_known",
				"previous_year": "previous_year_known",
				"difference": "previous_period_known",
				"difference_percent": "previous_period_known",
			},
		)
		comparison = fields("vat_return_comparison")
		for fieldname, flag in pairs.items():
			with self.subTest(field=fieldname):
				self.assertIn(comparison[fieldname]["fieldtype"], ("Currency", "Percent"))
				self.assertEqual((comparison[flag]["fieldtype"], comparison[flag]["hidden"]), ("Check", 1))
