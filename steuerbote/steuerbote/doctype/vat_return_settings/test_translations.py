"""Every text the VAT Return Settings and the file for Mein ELSTER show has a German translation in
translations/de.csv."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.elster import STATES, ustva_xml
from steuerbote.steuerbote.doctype.vat_return_settings.rules import MESSAGES

APP = Path(__file__).resolve().parents[3]
TRANSLATIONS = APP / "translations" / "de.csv"
DOCTYPES = ("vat_return_settings", "vat_return_period_rule", "vat_return_prepayment")
CONTROLLER = APP / "steuerbote" / "doctype" / "vat_return_settings" / "vat_return_settings.py"
VAT_RETURN = APP / "steuerbote" / "doctype" / "vat_return"
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
TRANSLATED_LITERAL = re.compile(r'\b_{1,2}\("((?:[^"\\]|\\.)*)"\)')
PLACEHOLDER = re.compile(r"\{\w+\}")


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


def texts_of_the_import_file() -> set[str]:
	"""The messages of the ELSTER XML and what the VAT Return shows of its file for Mein ELSTER."""
	scripts = "".join(
		(VAT_RETURN / name).read_text(encoding="utf-8") for name in ("vat_return.py", "vat_return.js")
	)
	further_details = (
		field
		for field in doctype("vat_return")["fields"]
		if field["fieldname"] in ("kz500_begruendung", "regelbesteuerung_from")
	)
	return (
		set(ustva_xml.MESSAGES)
		| set(ustva_xml.LABELS)
		| {text for text in TRANSLATED_LITERAL.findall(scripts) if "Mein ELSTER" in text}
		| {field[key] for field in further_details for key in ("label", "description")}
	)


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

	def test_every_text_of_the_file_for_mein_elster_is_translated(self):
		translated = {source for source, *_ in rows()}
		self.assertIn("XML for Mein ELSTER", texts_of_the_import_file())
		self.assertIn("Date of the Switch to the Regelbesteuerung (Kz 70)", texts_of_the_import_file())
		self.assertEqual(sorted(texts_of_the_import_file() - translated), [])

	def test_translations_keep_the_placeholders(self):
		for source, translation in rows():
			with self.subTest(source=source):
				self.assertCountEqual(PLACEHOLDER.findall(translation), PLACEHOLDER.findall(source))
