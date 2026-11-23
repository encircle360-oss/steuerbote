"""The files of the base of the annual documents, read without a bench: the child DocType Annual Filing Finding, the
methods the forms call and the German of every text."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.jahresmeldung import findings
from steuerbote.jahresmeldung.findings import Severity

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote"
BASE = MODULE / "annual_filing.py"
FINDING = MODULE / "doctype" / "annual_filing_finding" / "annual_filing_finding.json"
TRANSLATIONS = APP / "translations" / "de.csv"
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
# Labels Frappe translates itself; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset({"Code", "Kind", "Message", "Reference"})


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def translated() -> set[str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return {source for source, *_ in csv.reader(file)}


def definition_texts(definition: dict) -> set[str]:
	texts = {text for text in (definition["name"], definition.get("description")) if text}
	for field in definition["fields"]:
		texts.update(field[key] for key in ("label", "description") if field.get(key))
	return texts


class FindingFilesTest(TestCase):
	"""The table Befunde of every annual document: Art, Sperrt, Code, Nachricht and Referenz of each finding."""

	def setUp(self):
		self.definition = read_json(FINDING)
		self.fields = {field["fieldname"]: field for field in self.definition["fields"]}

	def test_is_a_child_table_of_the_module(self):
		self.assertEqual(
			(self.definition["name"], self.definition["istable"], self.definition["module"]),
			("Annual Filing Finding", 1, "Steuerbote"),
		)

	def test_holds_the_rows_the_core_writes(self):
		row = findings.rows([findings.Finding("SB-X", Severity.ERROR, "Text", "Konto 1590")])[0]
		self.assertEqual(self.definition["field_order"], list(row))
		self.assertEqual(list(self.fields), list(row))

	def test_names_art_sperrt_code_nachricht_and_referenz(self):
		self.assertEqual(
			{name: (field["fieldtype"], field["label"]) for name, field in self.fields.items()},
			{
				"severity": ("Select", "Kind"),
				"blocking": ("Check", "Blocking"),
				"code": ("Data", "Code"),
				"text": ("Small Text", "Message"),
				"reference": ("Data", "Reference"),
			},
		)

	def test_the_kinds_are_the_severities_of_the_core(self):
		self.assertEqual(
			self.fields["severity"]["options"].split("\n"), [severity.value for severity in Severity]
		)

	def test_only_steuerbote_writes_a_finding_and_the_grid_shows_all_of_it(self):
		for name, field in self.fields.items():
			with self.subTest(field=name):
				self.assertEqual((field.get("read_only"), field.get("in_list_view")), (1, 1))
		self.assertLessEqual(sum(field["columns"] for field in self.fields.values()), 10)


class BaseFilesTest(TestCase):
	def setUp(self):
		self.source = BASE.read_text(encoding="utf-8")

	def test_the_methods_a_form_calls_are_whitelisted_for_post(self):
		for method in ("calculate", "make_correction", "mark_filed_outside"):
			with self.subTest(method=method):
				self.assertRegex(self.source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')

	def test_every_text_of_the_base_is_translated(self):
		texts = set(TRANSLATED_LITERAL.findall(self.source)) | definition_texts(read_json(FINDING))
		self.assertIn("Calculate {0} before filing it.", texts)
		self.assertEqual(sorted(texts - translated() - FRAMEWORK_LABELS), [])

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & translated()), [])
