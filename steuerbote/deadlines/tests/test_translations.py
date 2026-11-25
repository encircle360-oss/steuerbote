"""Every text the deadlines show has a German translation in translations/de.csv: the report Offene Fristen, the
reminder and its e-mail with the notes of the annual deadlines, the Deadline Reminder, the reminder fields of the VAT
Return Settings and the entries of the workspace and the sidebar."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.deadlines import Kind, Note, Status

APP = Path(__file__).resolve().parents[2]
MODULE = APP / "steuerbote"
TRANSLATIONS = APP / "translations" / "de.csv"
REPORT = MODULE / "report" / "offene_fristen"
REMINDER = MODULE / "doctype" / "deadline_reminder"
SETTINGS = MODULE / "doctype" / "vat_return_settings" / "vat_return_settings.json"
WORKSPACE = MODULE / "workspace" / "steuern" / "steuern.json"
SIDEBAR = MODULE / "sidebar" / "steuerbote" / "steuerbote.json"
REPORT_NAME = "Offene Fristen"
REMINDER_FIELDS = ("deadlines_section", "deadline_recipients", "column_break_deadlines", "reminder_days")
# Labels Frappe and ERPNext translate themselves; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset({"Sent On", "Status"})
# The name of the report, the kinds and the status of a deadline read the same in every language.
GERMAN_NAMES = frozenset({REPORT_NAME} | {kind.value for kind in Kind} | {status.value for status in Status})
# The desk cuts a label after about 22 characters, in the sidebar as on a shortcut card.
LONGEST_LABEL = 20
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
PLACEHOLDER = re.compile(r"\{\w*\}")


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def literals(*paths: Path) -> set[str]:
	return {text for path in paths for text in TRANSLATED_LITERAL.findall(path.read_text(encoding="utf-8"))}


def field_texts(fields: list[dict]) -> set[str]:
	texts = {field[key] for field in fields for key in ("label", "description") if field.get(key)}
	options = {
		option
		for field in fields
		if field["fieldtype"] == "Select"
		for option in field["options"].split("\n")
		if option
	}
	return texts | options


def untranslated(texts: set[str]) -> list[str]:
	return sorted(texts - set(translations()) - FRAMEWORK_LABELS - GERMAN_NAMES)


def german(text: str) -> str:
	return translations().get(text, text)


class TranslationsTest(TestCase):
	def test_every_text_of_the_report_is_translated(self):
		texts = literals(REPORT / "offene_fristen.py", REPORT / "offene_fristen.js")
		self.assertIn("Days Ahead", texts)
		self.assertEqual(untranslated(texts), [])

	def test_every_text_of_the_reminder_and_its_e_mail_is_translated(self):
		texts = literals(MODULE / "deadlines.py")
		self.assertIn("Steuerbote: open deadlines of {0}", texts)
		self.assertIn("Kind of Deadline", texts)
		self.assertEqual(untranslated(texts), [])

	def test_every_text_of_the_deadline_reminder_is_translated(self):
		doctype = read_json(REMINDER / "deadline_reminder.json")
		texts = {doctype["name"], doctype["description"]} | field_texts(doctype["fields"])
		texts |= literals(REMINDER / "deadline_reminder.py")
		self.assertEqual(untranslated(texts), [])
		self.assertEqual(german(doctype["name"]), "Fristerinnerung")

	def test_every_text_of_the_reminder_fields_of_the_settings_is_translated(self):
		fields = [field for field in read_json(SETTINGS)["fields"] if field["fieldname"] in REMINDER_FIELDS]
		self.assertEqual(len(fields), len(REMINDER_FIELDS))
		self.assertEqual(untranslated(field_texts(fields)), [])

	def test_the_entries_of_the_desk_read_short_in_german(self):
		blocks = json.loads(read_json(WORKSPACE)["content"])
		(header,) = [
			re.sub(r"<[^>]+>", "", block["data"]["text"])
			for block in blocks
			if block["type"] == "header" and "Deadlines" in block["data"]["text"]
		]
		items = {
			item["link_to"]: item["label"] for item in read_json(SIDEBAR)["items"] if item["type"] == "Link"
		}
		labels = [header, items["Deadline Reminder"], items[REPORT_NAME]]
		self.assertEqual(untranslated(set(labels)), [])
		self.assertEqual(
			[german(label) for label in labels], ["Fristen", "Fristerinnerungen", "Offene Fristen"]
		)
		self.assertEqual([label for label in labels if len(german(label)) > LONGEST_LABEL], [])

	def test_every_note_of_a_deadline_has_a_text(self):
		tree = ast.parse((MODULE / "deadlines.py").read_text(encoding="utf-8"))
		(function,) = [
			node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "note_texts"
		]
		(returned,) = [node.value for node in ast.walk(function) if isinstance(node, ast.Return)]
		self.assertIsInstance(returned, ast.Dict)
		self.assertEqual([key.attr for key in returned.keys], [note.name for note in Note])

	def test_the_new_columns_read_short_in_german(self):
		self.assertEqual(
			[german("State of the Document"), german("Deadline Note")], ["Stand des Belegs", "Hinweis"]
		)

	def test_translations_keep_the_placeholders(self):
		texts = literals(
			MODULE / "deadlines.py", REPORT / "offene_fristen.py", REMINDER / "deadline_reminder.py"
		)
		for source in texts - FRAMEWORK_LABELS:
			with self.subTest(source=source):
				self.assertCountEqual(PLACEHOLDER.findall(german(source)), PLACEHOLDER.findall(source))


class SetupStepTranslationsTest(TestCase):
	def test_every_note_of_the_setup_step_of_the_deadlines_is_translated(self):
		"""Steuerbote einrichten shows the notes of check_setup through _() of their templates."""
		tree = ast.parse((MODULE / "deadlines.py").read_text(encoding="utf-8"))
		constants = {
			node.targets[0].id: node.value.value
			for node in tree.body
			if isinstance(node, ast.Assign)
			and isinstance(node.targets[0], ast.Name)
			and isinstance(node.value, ast.Constant)
			and isinstance(node.value.value, str)
		}
		(messages,) = (
			node.value
			for node in tree.body
			if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "SETUP_MESSAGES"
		)
		texts = {constants[element.id] for element in messages.elts}
		self.assertEqual(len(texts), 7)
		self.assertEqual(untranslated(texts | {"Deadlines and Reminder"}), [])
