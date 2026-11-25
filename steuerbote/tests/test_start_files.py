"""The files of a start with Steuerbote in the middle of a company's life (steuerbote/setup/start.py), read without a
bench: the Voranmeldung filed before Steuerbote with who entered it and from what, the start of the books in the VAT
Return Settings, the column of the base of the Dauerfristverlängerung, the step of the setup, and the German of every
text."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote import hooks
from steuerbote.setup import start

APP = Path(__file__).resolve().parents[1]
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
CONTROLLER = DOCTYPES / "vat_return_prior_filing" / "vat_return_prior_filing.py"
SETTINGS_CONTROLLER = DOCTYPES / "vat_return_settings" / "vat_return_settings.py"
TRANSLATED_LITERAL = re.compile(r"\b_\(\s*\"((?:[^\"\\]|\\.)*)\"")
PLACEHOLDER = re.compile(r"\{\d*\}")
# Labels Frappe and ERPNext translate themselves, and terms that read the same in German.
FRAMEWORK_LABELS = frozenset(
	{"Amended From", "Company", "Year", "Series", "Reason", "Kz 39", "Kz 83", "Steuernummer"}
)


def definition(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def fields(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in definition(name)["fields"]}


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


class PriorFilingDocTypeTest(TestCase):
	def setUp(self):
		self.definition = definition("vat_return_prior_filing")
		self.fields = fields("vat_return_prior_filing")

	def test_is_a_document_that_counts_once_submitted(self):
		self.assertEqual(self.definition["name"], "VAT Return Prior Filing")
		self.assertEqual(self.definition["is_submittable"], 1)
		self.assertEqual(self.definition["autoname"], "naming_series:")
		self.assertEqual(self.fields["naming_series"]["options"], "VVS-.{year}.-.#####")
		self.assertEqual(self.fields["amended_from"]["options"], "VAT Return Prior Filing")

	def test_holds_the_period_and_the_amounts_as_filed(self):
		for name in ("company", "year", "rhythm", "period_index", "filed_on"):
			with self.subTest(field=name):
				self.assertEqual(self.fields[name].get("reqd"), 1)
		self.assertEqual(self.fields["rhythm"]["options"], "monthly\nquarterly")
		for name in ("kz83", "kz39", "kz41", "kz42", "kz21"):
			with self.subTest(field=name):
				self.assertEqual(self.fields[name]["fieldtype"], "Currency")
		self.assertEqual(self.fields["kz39"].get("non_negative"), 1)

	def test_names_its_source_its_reason_and_who_entered_it_when(self):
		self.assertEqual((self.fields["source_document"]["reqd"], self.fields["reason"]["reqd"]), (1, 1))
		self.assertEqual(self.fields["attachment"]["fieldtype"], "Attach")
		for name in ("entered_by", "entered_on", "period_label"):
			with self.subTest(field=name):
				self.assertEqual(self.fields[name]["read_only"], 1)
		self.assertEqual(self.fields["entered_by"]["options"], "User")

	def test_an_accounts_user_reads_it_and_changes_nothing(self):
		(user,) = (row for row in self.definition["permissions"] if row["role"] == "Accounts User")
		self.assertEqual(user.get("read"), 1)
		self.assertFalse(user.get("create") or user.get("write") or user.get("submit") or user.get("cancel"))

	def test_the_base_of_the_dauerfristverlaengerung_links_it(self):
		base = fields("vat_return_extension_base")
		self.assertEqual(
			(base["prior_filing"]["fieldtype"], base["prior_filing"]["options"]),
			("Link", "VAT Return Prior Filing"),
		)

	def test_the_settings_hold_the_start_of_the_books(self):
		settings = fields("vat_return_settings")
		self.assertEqual(settings["books_start"]["fieldtype"], "Date")
		self.assertFalse(settings["books_start"].get("reqd"))


class SetupStepTest(TestCase):
	def test_the_hook_runs_the_start_after_the_settings_and_the_mapping(self):
		(entry,) = (entry for entry in hooks.steuerbote_setup_steps if entry["key"] == "books_start")
		self.assertEqual(
			entry,
			{
				"key": "books_start",
				"label": "Start in Steuerbote",
				"order": 35,
				"needs": ["vat_return_settings", "vat_return_mapping"],
				"run": "steuerbote.steuerbote.setup.check_books_start",
			},
		)


class TranslationsTest(TestCase):
	def texts(self) -> set[str]:
		found = set()
		for name in ("vat_return_prior_filing", "vat_return_settings", "vat_return_extension_base"):
			found.add(definition(name)["name"])
			for field in definition(name)["fields"]:
				found.update(text for text in (field.get("label"), field.get("description")) if text)
		found.update(TRANSLATED_LITERAL.findall(CONTROLLER.read_text(encoding="utf-8")))
		found.update(TRANSLATED_LITERAL.findall(SETTINGS_CONTROLLER.read_text(encoding="utf-8")))
		found.update(start.MESSAGES)
		found.update({"Prior Filings", "VAT Return Prior Filings", "Start in Steuerbote"})
		return found

	def test_every_text_reads_in_german(self):
		self.assertEqual(sorted(self.texts() - translations().keys() - FRAMEWORK_LABELS), [])

	def test_the_translations_keep_the_placeholders(self):
		german = translations()
		for text in self.texts() - FRAMEWORK_LABELS:
			with self.subTest(text=text):
				self.assertCountEqual(PLACEHOLDER.findall(german[text]), PLACEHOLDER.findall(text))

	def test_the_record_reads_as_what_it_is(self):
		german = translations()
		self.assertEqual(german["VAT Return Prior Filing"], "Voranmeldung vor Steuerbote")
		self.assertEqual(german["Books Start"], "Bücher in ERPNext ab")
