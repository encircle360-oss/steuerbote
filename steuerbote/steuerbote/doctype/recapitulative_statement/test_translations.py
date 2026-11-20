"""Every text of the Zusammenfassende Meldung, its USt-IdNr.-Bestätigungen and the rules of the core it shows
has a German translation in translations/de.csv."""

import csv
import importlib
import json
import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[3]
MODULE = APP / "steuerbote"
TRANSLATIONS = APP / "translations" / "de.csv"
DOCTYPES = (
	"recapitulative_statement",
	"recapitulative_statement_line",
	"recapitulative_statement_voucher",
	"recapitulative_statement_reconciliation",
	"recapitulative_statement_comparison",
	"recapitulative_statement_hint",
	"vat_id_confirmation",
	"zm_rule",
)
SETTINGS_FIELDS = ("ust_idnr", "zm_rules")
SOURCES = (
	"doctype/recapitulative_statement/recapitulative_statement.py",
	"doctype/recapitulative_statement/recapitulative_statement.js",
	"doctype/vat_id_confirmation/vat_id_confirmation.py",
)
# The status, the kinds of a statement and of a finding, the Arten and the results of a qualified query read
# the same in every language, like the status of a VAT Return.
UNTRANSLATED = frozenset(
	{
		"Entwurf",
		"Berechnet",
		"Bereit",
		"Abgegeben",
		"Ersetzt",
		"Erstmeldung",
		"Berichtigung",
		"Fehler",
		"Hinweis",
		"Transferticket",
		"L",
		"D",
		"S",
		"A",
		"B",
		"C",
		"ZM-.YYYY.-.#####",
	}
)
# Labels Frappe and ERPNext translate themselves; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{
		"Amended From",
		"Code",
		"Company Name",
		"Customer",
		"Difference",
		"Due Date",
		"From Date",
		"Kind",
		"Message",
		"Party",
		"Reason",
		"Remarks",
		"Series",
		"Service",
		"Status",
		"To Date",
		"Totals",
		"User",
		"Valid From",
		"Voucher No",
		"Voucher Type",
	}
)
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
CORE_TEMPLATE = re.compile(r"\bZmError\(([A-Z][A-Z_]*)\b")


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def doctype(name: str) -> dict:
	return json.loads((MODULE / "doctype" / name / f"{name}.json").read_text(encoding="utf-8"))


def field_texts(fields) -> set[str]:
	texts = set()
	for field in fields:
		texts.update(field[key] for key in ("label", "description") if field.get(key))
		if field["fieldtype"] == "Select":
			texts.update(option for option in field["options"].split("\n") if option)
	return texts


def texts_of_the_doctypes() -> set[str]:
	texts = set()
	for name in DOCTYPES:
		definition = doctype(name)
		texts.update(text for text in (definition["name"], definition.get("description")) if text)
		texts.update(field_texts(definition["fields"]))
	settings = doctype("vat_return_settings")["fields"]
	texts.update(field_texts(field for field in settings if field["fieldname"] in SETTINGS_FIELDS))
	return texts


def texts_of_the_sources() -> set[str]:
	texts = set()
	for source in SOURCES:
		texts.update(TRANSLATED_LITERAL.findall((MODULE / source).read_text(encoding="utf-8")))
	return texts


def templates_of_the_core() -> set[str]:
	"""The messages of every ZmError the core of the ZM raises, which the Frappe layer translates."""
	templates = set()
	for path in sorted((APP / "zm").glob("*.py")):
		module = importlib.import_module(f"steuerbote.zm.{path.stem}")
		for name in CORE_TEMPLATE.findall(path.read_text(encoding="utf-8")):
			templates.add(getattr(module, name))
	return templates


class ZmTranslationsTest(TestCase):
	def test_the_sources_are_read(self):
		for text, found in (
			("Recapitulative Statement", texts_of_the_doctypes()),
			("Confirm VAT IDs", texts_of_the_sources()),
			("A Zusammenfassende Meldung needs at least one Meldezeile.", templates_of_the_core()),
		):
			with self.subTest(text=text):
				self.assertIn(text, found)

	def test_every_text_of_the_doctypes_is_translated(self):
		missing = texts_of_the_doctypes() - set(translations()) - UNTRANSLATED - FRAMEWORK_LABELS
		self.assertEqual(sorted(missing), [])

	def test_every_text_of_the_controllers_and_the_form_is_translated(self):
		missing = texts_of_the_sources() - set(translations()) - UNTRANSLATED - FRAMEWORK_LABELS
		self.assertEqual(sorted(missing), [])

	def test_every_rule_of_the_core_is_translated(self):
		self.assertEqual(sorted(templates_of_the_core() - set(translations())), [])

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & set(translations())), [])

	def test_the_labels_read_as_the_law_names_them(self):
		german = translations()
		self.assertEqual(
			[
				german[text]
				for text in ("Recapitulative Statement", "VAT ID", "VAT ID Confirmation", "Confirm VAT IDs")
			],
			["Zusammenfassende Meldung", "USt-IdNr.", "USt-IdNr.-Bestätigung", "USt-IdNrn. prüfen"],
		)
