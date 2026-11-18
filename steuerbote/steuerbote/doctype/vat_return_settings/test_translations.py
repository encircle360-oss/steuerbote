"""Every text the VAT Return Settings show has a German translation in translations/de.csv."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.elster import STATES
from steuerbote.steuerbote.doctype.vat_return_settings.rules import MESSAGES

APP = Path(__file__).resolve().parents[3]
TRANSLATIONS = APP / "translations" / "de.csv"
DOCTYPES = ("vat_return_settings", "vat_return_period_rule", "vat_return_prepayment")
CONTROLLER = APP / "steuerbote" / "doctype" / "vat_return_settings" / "vat_return_settings.py"
# German terms and values that every language shows as they are.
UNTRANSLATED = frozenset(
	{
		"Dauerfristverlängerung",
		"Sondervorauszahlung",
		"Steuernummer",
		"SKR03",
		"SKR04",
		"Eigener Kontenrahmen",
		"Soll",
	}
	| set(STATES.values())
)
TRANSLATED_LITERAL = re.compile(r'\b_\("((?:[^"\\]|\\.)*)"\)')
PLACEHOLDER = re.compile(r"\{\d+\}")


def rows() -> list[list[str]]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return list(csv.reader(file))


def doctype(name: str) -> dict:
	return json.loads((APP / "steuerbote" / "doctype" / name / f"{name}.json").read_text(encoding="utf-8"))


def texts_of_the_settings() -> set[str]:
	texts = set(MESSAGES) | set(TRANSLATED_LITERAL.findall(CONTROLLER.read_text(encoding="utf-8")))
	for name in DOCTYPES:
		definition = doctype(name)
		texts.add(definition["name"])
		for field in definition["fields"]:
			texts.update(field[key] for key in ("label", "description") if field.get(key))
			if field["fieldtype"] == "Select":
				texts.update(option for option in field["options"].split("\n") if option)
	return texts - UNTRANSLATED


class TranslationsTest(TestCase):
	def test_every_row_pairs_a_source_with_its_translation(self):
		for row in rows():
			with self.subTest(row=row):
				self.assertEqual(len(row), 2)
				for text in row:
					self.assertTrue(text)
					self.assertEqual(text, text.strip())

	def test_rows_are_sorted_by_source_and_each_source_appears_once(self):
		sources = [source for source, *_ in rows()]
		self.assertEqual(sources, sorted(set(sources)))

	def test_every_text_of_the_settings_is_translated(self):
		translated = {source for source, *_ in rows()}
		self.assertEqual(sorted(texts_of_the_settings() - translated), [])

	def test_translations_keep_the_placeholders(self):
		for source, translation in rows():
			with self.subTest(source=source):
				self.assertCountEqual(PLACEHOLDER.findall(translation), PLACEHOLDER.findall(source))
