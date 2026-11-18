"""The standard records the app ships fit together, read from their files without a bench.

Frappe imports them on install without checking, for example, that a workspace block names an existing
shortcut or that a filter of a report reaches its Python.
"""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote"
TRANSLATIONS = APP / "translations" / "de.csv"
REPORT = MODULE / "report" / "ustva_kennzahlen"

# Names of the app that read the same in every language.
GERMAN_NAMES = frozenset({"Steuern", "Offene Voranmeldungen", "UStVA Kennzahlen"})
# Labels Frappe and ERPNext translate themselves; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{
		"Account",
		"Company",
		"Credit",
		"Currency",
		"Debit",
		"Posting Date",
		"Setup",
		"Voucher No",
		"Voucher Type",
	}
)
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def translated() -> set[str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return {source for source, *_ in csv.reader(file)}


def doctype_names() -> set[str]:
	return {read_json(path)["name"] for path in (MODULE / "doctype").glob("*/*.json")}


def untranslated(texts: set[str]) -> list[str]:
	return sorted(texts - translated() - GERMAN_NAMES - FRAMEWORK_LABELS)


class ReportFilesTest(TestCase):
	def test_the_report_is_a_standard_script_report_of_the_vat_return(self):
		report = read_json(REPORT / "ustva_kennzahlen.json")
		self.assertEqual(
			{
				key: report[key]
				for key in ("name", "report_name", "report_type", "ref_doctype", "is_standard", "module")
			},
			{
				"name": "UStVA Kennzahlen",
				"report_name": "UStVA Kennzahlen",
				"report_type": "Script Report",
				"ref_doctype": "VAT Return",
				"is_standard": "Yes",
				"module": "Steuerbote",
			},
		)
		self.assertIn("VAT Return", doctype_names())

	def test_the_filters_of_the_script_are_those_the_report_reads(self):
		script = (REPORT / "ustva_kennzahlen.js").read_text(encoding="utf-8")
		source = (REPORT / "ustva_kennzahlen.py").read_text(encoding="utf-8")
		fieldnames = re.findall(r'fieldname: "(\w+)"', script)
		self.assertEqual(fieldnames, ["company", "year", "rhythm", "period_index"])
		assignments = {
			target.id: node.value
			for node in ast.parse(source).body
			if isinstance(node, ast.Assign)
			for target in node.targets
			if isinstance(target, ast.Name)
		}
		self.assertEqual(list(ast.literal_eval(assignments["FILTERS"])), fieldnames)

	def test_every_label_of_the_report_is_translated(self):
		texts = set()
		for name in ("ustva_kennzahlen.js", "ustva_kennzahlen.py"):
			texts.update(TRANSLATED_LITERAL.findall((REPORT / name).read_text(encoding="utf-8")))
		self.assertIn("Ledger Amount", texts)
		self.assertEqual(untranslated(texts), [])
