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

from steuerbote.ustva import KENNZAHLEN

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote"
TRANSLATIONS = APP / "translations" / "de.csv"
REPORT = MODULE / "report" / "ustva_kennzahlen"
WORKSPACE = MODULE / "workspace" / "steuern" / "steuern.json"
NUMBER_CARDS = MODULE / "number_card"
PRINT_FORMAT = MODULE / "print_format" / "umsatzsteuer_voranmeldung"
VAT_RETURN_SCRIPT = MODULE / "doctype" / "vat_return" / "vat_return.js"

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
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
CLASS_ATTRIBUTE = re.compile(r'\bclass="([^"]*)"')
CLASS_SELECTOR = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
# Frappe's print stylesheet styles bare classes such as .label (inline, 75 %, bold), so the print format
# names its classes with a prefix of its own.
PRINT_CLASS_PREFIX = "sb-"


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def translated() -> set[str]:
	return set(translations())


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

	def test_the_vat_return_opens_the_report_with_its_own_period(self):
		script = (MODULE / "doctype" / "vat_return" / "vat_return.js").read_text(encoding="utf-8")
		route = re.search(
			r'frappe\.set_route\("query-report", "UStVA Kennzahlen", \{(?P<filters>[^}]*)\}', script
		)
		self.assertIsNotNone(route)
		self.assertEqual(
			re.findall(r"(\w+): frm\.doc\.(\w+)", route["filters"]),
			[(field, field) for field in ("company", "year", "rhythm", "period_index")],
		)

	def test_every_label_of_the_report_is_translated(self):
		texts = set()
		for name in ("ustva_kennzahlen.js", "ustva_kennzahlen.py"):
			texts.update(TRANSLATED_LITERAL.findall((REPORT / name).read_text(encoding="utf-8")))
		self.assertIn("Ledger Amount", texts)
		self.assertEqual(untranslated(texts), [])


class WorkspaceFilesTest(TestCase):
	def setUp(self):
		self.workspace = read_json(WORKSPACE)
		self.blocks = json.loads(self.workspace["content"])

	def test_the_workspace_belongs_to_the_module(self):
		self.assertEqual(
			{key: self.workspace[key] for key in ("name", "label", "title", "module", "public", "type")},
			{
				"name": "Steuern",
				"label": "Steuern",
				"title": "Steuern",
				"module": "Steuerbote",
				"public": 1,
				"type": "Workspace",
			},
		)

	def test_every_block_names_a_shortcut_or_number_card_of_the_workspace(self):
		shortcuts = {shortcut["label"] for shortcut in self.workspace["shortcuts"]}
		cards = {card["label"] for card in self.workspace["number_cards"]}
		named = {
			"shortcut": [
				block["data"]["shortcut_name"] for block in self.blocks if block["type"] == "shortcut"
			],
			"number_card": [
				block["data"]["number_card_name"] for block in self.blocks if block["type"] == "number_card"
			],
		}
		self.assertEqual(sorted(named["shortcut"]), sorted(shortcuts))
		self.assertEqual(sorted(named["number_card"]), sorted(cards))
		self.assertEqual(len({block["id"] for block in self.blocks}), len(self.blocks))

	def test_the_shortcuts_open_the_vat_return_its_setup_and_the_report(self):
		targets = {
			(shortcut["type"], shortcut["link_to"], shortcut.get("doc_view", ""))
			for shortcut in self.workspace["shortcuts"]
		}
		self.assertEqual(
			targets,
			{
				("DocType", "VAT Return", "New"),
				("DocType", "VAT Return", "List"),
				("DocType", "VAT Return Settings", "List"),
				("DocType", "VAT Return Mapping", "List"),
				("Report", "UStVA Kennzahlen", ""),
			},
		)
		doctypes = doctype_names()
		for kind, target, _view in targets:
			with self.subTest(target=target):
				if kind == "DocType":
					self.assertIn(target, doctypes)
				else:
					self.assertEqual(read_json(REPORT / "ustva_kennzahlen.json")["name"], target)

	def test_the_number_card_counts_vat_returns_in_draft(self):
		(row,) = self.workspace["number_cards"]
		card = read_json(NUMBER_CARDS / "offene_voranmeldungen" / "offene_voranmeldungen.json")
		self.assertEqual(row["number_card_name"], card["name"])
		self.assertEqual(
			{
				key: card[key]
				for key in ("label", "type", "document_type", "function", "is_standard", "module")
			},
			{
				"label": "Offene Voranmeldungen",
				"type": "Document Type",
				"document_type": "VAT Return",
				"function": "Count",
				"is_standard": 1,
				"module": "Steuerbote",
			},
		)
		self.assertEqual(json.loads(card["filters_json"]), [["VAT Return", "docstatus", "=", "0"]])

	def test_every_text_of_the_workspace_is_translated(self):
		headers = {
			re.sub(r"<[^>]+>", "", block["data"]["text"])
			for block in self.blocks
			if block["type"] == "header"
		}
		labels = {shortcut["label"] for shortcut in self.workspace["shortcuts"]}
		self.assertEqual(untranslated(headers | labels), [])


class PrintFormatFilesTest(TestCase):
	def setUp(self):
		self.record = read_json(PRINT_FORMAT / "umsatzsteuer_voranmeldung.json")
		self.template = (PRINT_FORMAT / "umsatzsteuer_voranmeldung.html").read_text(encoding="utf-8")

	def test_the_print_format_is_a_standard_jinja_format_of_the_vat_return(self):
		self.assertEqual(
			{
				key: self.record[key]
				for key in ("name", "doc_type", "print_format_type", "standard", "module", "custom_format")
			},
			{
				"name": "Umsatzsteuer-Voranmeldung",
				"doc_type": "VAT Return",
				"print_format_type": "Jinja",
				"standard": "Yes",
				"module": "Steuerbote",
				"custom_format": 0,
			},
		)

	def test_prints_on_a4_in_black_and_grey(self):
		css = self.record["css"] + self.template
		self.assertIn("size: A4 portrait", self.record["css"])
		colours = HEX_COLOUR.findall(css)
		self.assertTrue(colours)
		for colour in colours:
			with self.subTest(colour=colour):
				channels = colour if len(colour) == 3 else (colour[0:2], colour[2:4], colour[4:6])
				self.assertEqual(len(set(channels)), 1)
		self.assertNotIn("<img", self.template)
		self.assertNotRegex(css, r"\b(rgb|hsl)a?\(")

	def test_keeps_to_classes_of_its_own(self):
		used = {name for value in CLASS_ATTRIBUTE.findall(self.template) for name in value.split()}
		styled = set(CLASS_SELECTOR.findall(self.record["css"]))
		self.assertNotIn("label", used | styled)
		self.assertEqual(
			sorted(name for name in used | styled if not name.startswith(PRINT_CLASS_PREFIX)), []
		)
		self.assertEqual(sorted(used), sorted(styled))

	def test_the_header_pairs_each_label_with_its_value(self):
		labels = re.findall(r'<tr><td class="sb-label">([^<]+)</td><td class="sb-value">', self.template)
		self.assertEqual(
			labels,
			[
				"Unternehmen",
				"Steuernummer",
				"Steuernummer im ELSTER-Format",
				"Finanzamt",
				"Voranmeldungszeitraum",
				"Fällig am",
				"Meldung",
			],
		)

	def test_the_labels_of_the_flags_are_those_of_the_catalogue(self):
		for number in ("10", "22", "29", "26"):
			with self.subTest(kennzahl=number):
				self.assertIn(f'"{KENNZAHLEN[number].label}"', self.template)
		self.assertIn(KENNZAHLEN["500"].label, self.template)
		self.assertIn(f'"{KENNZAHLEN["83"].label}", "83"', self.template)

	def test_the_derived_rates_are_those_of_the_catalogue(self):
		rates = {
			number: int(kennzahl.rate) for number, kennzahl in KENNZAHLEN.items() if kennzahl.derives_tax
		}
		self.assertIn(
			"{%- set derived_rates = {"
			+ ", ".join(f'"{number}": {rate}' for number, rate in rates.items())
			+ "} -%}",
			self.template,
		)


class VatReturnFormFilesTest(TestCase):
	"""A draft is filed through ELSTER or a note of its filing, never by Buchen alone."""

	def setUp(self):
		self.script = VAT_RETURN_SCRIPT.read_text(encoding="utf-8")

	def test_a_draft_gets_no_hint_to_submit_it(self):
		setup = re.search(r"\n\tsetup\(frm\) \{\n(?P<body>.*?)\n\t\},\n", self.script, re.DOTALL)
		self.assertIsNotNone(setup)
		self.assertIn("frm.show_submit_message = () => {};", setup["body"])

	def test_a_return_ready_to_file_says_how_to_file_it(self):
		(note,) = re.findall(r'__\("(Ready to file: [^"]*)"\)', self.script)
		self.assertEqual(
			translations()[note],
			"Bereit zur Abgabe: XML für Mein ELSTER erzeugen oder über ELSTER übermitteln.",
		)
		self.assertRegex(self.script, r'frm\.doc\.status === "Bereit"')
