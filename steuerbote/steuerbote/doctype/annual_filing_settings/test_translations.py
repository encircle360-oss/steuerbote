"""Every text the Annual Filing Settings show has a German translation in translations/de.csv."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.elster import STATES
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import MESSAGES

APP = Path(__file__).resolve().parents[3]
TRANSLATIONS = APP / "translations" / "de.csv"
DOCTYPE_DIR = APP / "steuerbote" / "doctype"
SETTINGS = DOCTYPE_DIR / "annual_filing_settings"
# German terms and codes that read the same in every language.
UNTRANSLATED = frozenset(
	{
		"AO",
		"Abschlussstichtag",
		"Amtlicher Gemeindeschlüssel",
		"Arbeitnehmer",
		"Betriebsstätten",
		"Bilanzsumme",
		"E-Bilanz",
		"Gemeinde",
		"Gesellschafter-Geschäftsführer",
		"GewSt",
		"Gewerbesteuer",
		"GmbH",
		"GnR",
		"Groß",
		"HAOE",
		"HGBM",
		"HRA",
		"HRB",
		"Handelsregister",
		"Hebenummer",
		"Hebesatz (%)",
		"Hebesätze",
		"Hinterlegung",
		"Identifikationsnummer",
		"Jahresabschluss",
		"KSt",
		"Klein",
		"Kleinst",
		"Kleinunternehmer",
		"Mittelgroß",
		"PR",
		"SolZ",
		"Steuerberatung",
		"Steuernummer",
		"UG",
		"Umsatzerlöse",
		"VR",
		"Veröffentlichung",
		"Vorauszahlungen",
	}
	| set(STATES.values())
)
# Labels Frappe and ERPNext translate themselves; a row of the app would change them on every page of the site.
FRAMEWORK_LABELS = frozenset(
	{
		"Address",
		"Amount",
		"Confirmed",
		"Country",
		"Due Date",
		"First Name",
		"From Date",
		"Function",
		"Kind",
		"Reason",
		"Source",
		"Tax",
		"To Date",
	}
)
SCRIPT_LITERAL = re.compile(r"\b__\(\s*\"((?:[^\"\\]|\\.)*)\"")


def rows() -> list[list[str]]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return list(csv.reader(file))


def doctypes() -> list[dict]:
	return [
		json.loads(path.read_text(encoding="utf-8"))
		for path in sorted(DOCTYPE_DIR.glob("annual_filing_*/*.json"))
	]


def translated_literals(path: Path) -> set[str]:
	"""The first argument of every _() call of a Python module, implicit concatenations joined."""
	return {
		node.args[0].value
		for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
		if isinstance(node, ast.Call)
		and isinstance(node.func, ast.Name)
		and node.func.id == "_"
		and node.args
		and isinstance(node.args[0], ast.Constant)
		and isinstance(node.args[0].value, str)
	}


def texts_of_the_settings() -> set[str]:
	texts = set(MESSAGES) | translated_literals(SETTINGS / "annual_filing_settings.py")
	texts |= set(SCRIPT_LITERAL.findall((SETTINGS / "annual_filing_settings.js").read_text(encoding="utf-8")))
	for definition in doctypes():
		texts.add(definition["name"])
		texts.update(definition[key] for key in ("description",) if definition.get(key))
		for field in definition["fields"]:
			texts.update(field[key] for key in ("label", "description") if field.get(key))
			if field["fieldtype"] == "Select":
				texts.update(option for option in field["options"].split("\n") if option)
	return texts


class TranslationsTest(TestCase):
	def test_every_text_of_the_settings_is_translated(self):
		translated = {source for source, *_ in rows()}
		texts = texts_of_the_settings()
		self.assertIn("Take Address", texts)
		self.assertIn("{0} in row {1} of {2}", texts)
		self.assertEqual(sorted(texts - UNTRANSLATED - FRAMEWORK_LABELS - translated), [])

	def test_the_app_keeps_out_of_the_translations_of_the_framework(self):
		translated = {source for source, *_ in rows()}
		self.assertEqual(sorted(FRAMEWORK_LABELS & translated), [])
		self.assertLessEqual(FRAMEWORK_LABELS, texts_of_the_settings())

	def test_the_settings_read_as_the_annual_filings_name_them(self):
		german = dict(rows())
		self.assertEqual(
			[
				german[text]
				for text in ("Annual Filing Settings", "Shareholders", "Managing Directors", "Take Address")
			],
			["Einstellungen Jahresmeldungen", "Anteilseigner", "Geschäftsführer", "Anschrift übernehmen"],
		)
