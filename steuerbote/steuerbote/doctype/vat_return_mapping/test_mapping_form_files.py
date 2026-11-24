"""The form of the VAT Return Mapping, read from its files without a bench: the methods it calls are whitelisted
for POST, „Steuervorlagen prüfen“ and „Vorgaben aktualisieren“ read in German, their dialogs escape what the site
holds, and the rows for the annual return have their fields and read in German."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.mapping_sync import ANNUAL_RULE_FIELDS, CHECK_FIELDS, CHOICE_FIELDS, RULE_FIELDS
from steuerbote.mappings import transfer
from steuerbote.mappings.diff import Change, Origin
from steuerbote.ustjahr import split

APP = Path(__file__).resolve().parents[3]
FOLDER = APP / "steuerbote" / "doctype" / "vat_return_mapping"
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
DIFFERENCES_SCRIPT = APP / "public" / "js" / "mapping_differences.js"
# The forms of the three mappings, which include the dialog of the differences.
FORMS = (
	FOLDER / "vat_return_mapping.js",
	DOCTYPES / "income_tax_mapping" / "income_tax_mapping.js",
	DOCTYPES / "balance_sheet_mapping" / "balance_sheet_mapping.js",
)
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


class MappingFormFilesTest(TestCase):
	def setUp(self):
		self.script = (FOLDER / "vat_return_mapping.js").read_text(encoding="utf-8")
		self.source = (FOLDER / "vat_return_mapping.py").read_text(encoding="utf-8")

	def test_the_methods_the_form_calls_are_whitelisted_for_post(self):
		methods = sorted(set(re.findall(r'frm\.call\("(\w+)"', self.script)))
		self.assertEqual(
			methods,
			[
				"check_tax_templates",
				"compare_with_defaults",
				"compare_with_file",
				"export_mapping",
				"import_file",
				"load_defaults",
				"update_from_defaults",
				"watch_template_accounts",
			],
		)
		for method in methods:
			with self.subTest(method=method):
				self.assertRegex(self.source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')

	def test_the_check_reads_in_german(self):
		german = translations()
		self.assertEqual(german["Check Tax Templates"], "Steuervorlagen prüfen")
		self.assertEqual(german["Watch at the Level Blocking"], "Auf der Stufe „Sperrt“ beobachten")

	def test_the_dialog_escapes_numbers_names_and_templates_of_the_accounts(self):
		dialog = re.search(
			r"\nfunction show_template_accounts\(frm, accounts\) \{\n(?P<body>.*?)\n\}\n",
			self.script,
			re.DOTALL,
		)
		self.assertIsNotNone(dialog)
		body = dialog["body"]
		self.assertIn("const escape = frappe.utils.escape_html;", body)
		for value in ("account.account_number", "account.account_name", "account.templates"):
			with self.subTest(value=value):
				shown = re.findall(rf"\$\{{[^}}]*{re.escape(value)}[^}}]*\}}", body)
				self.assertTrue(shown)
				self.assertTrue(all("escape" in expression for expression in shown), shown)


def labels_of(source: str, name: str) -> dict[str, str]:
	"""A module-level dict of the source, keyed by the name of an enum member or by its text."""
	for node in ast.parse(source).body:
		if isinstance(node, ast.Assign) and [target.id for target in node.targets] == [name]:
			return {
				key.attr if isinstance(key, ast.Attribute) else key.value: value.value
				for key, value in zip(node.value.keys, node.value.values, strict=True)
			}
	raise AssertionError(f"{name} not found")


class DifferencesFilesTest(TestCase):
	"""Vorgaben aktualisieren and the dialog of the differences it shares with Zuordnung importieren."""

	def setUp(self):
		self.source = (FOLDER / "vat_return_mapping.py").read_text(encoding="utf-8")
		self.dialog = DIFFERENCES_SCRIPT.read_text(encoding="utf-8")
		self.script = (FOLDER / "vat_return_mapping.js").read_text(encoding="utf-8")

	def test_the_form_includes_the_dialog_of_the_differences(self):
		self.assertTrue(
			self.script.startswith('{% include "steuerbote/public/js/mapping_differences.js" %}\n')
		)

	def test_the_dialog_reads_in_german(self):
		german = translations()
		texts = set(TRANSLATED_LITERAL.findall(self.dialog))
		self.assertIn("Account or Tax Check", texts)
		self.assertEqual(sorted(texts - german.keys()), [])
		self.assertEqual(german["Update Defaults"], "Vorgaben aktualisieren")

	def test_every_change_origin_and_field_has_a_german_label(self):
		german = translations()
		changes = labels_of(self.source, "CHANGES")
		origins = labels_of(self.source, "ORIGINS")
		fields = labels_of(self.source, "FIELD_LABELS")
		self.assertEqual(set(changes), {change.name for change in Change})
		self.assertEqual(set(origins), {origin.name for origin in Origin})
		self.assertEqual(
			set(fields), {"place", "level", *RULE_FIELDS, *CHECK_FIELDS, *CHOICE_FIELDS, *ANNUAL_RULE_FIELDS}
		)
		labels = {*changes.values(), *origins.values(), *fields.values()}
		self.assertEqual(sorted(labels - german.keys()), [])

	def test_the_dialog_escapes_every_text_of_the_server(self):
		rows = re.search(r"const rows = differences\.map\((?P<body>.*?)\n\t\);\n", self.dialog, re.DOTALL)
		self.assertIsNotNone(rows)
		body = rows["body"]
		for value in ("id", "subject", "change", "fields", "current", "proposed", "origin"):
			with self.subTest(value=value):
				shown = re.findall(rf"\$\{{[^}}]*difference\.{value}\b[^}}]*\}}", body)
				self.assertTrue(shown)
				self.assertTrue(
					all("escape" in expression or expression.endswith("? `") for expression in shown), shown
				)
		self.assertIn("${escape(intro)}", self.dialog)
		self.assertIn("${escape(proposed_label)}", self.dialog)

	def test_the_button_of_vorgaben_aktualisieren_says_what_a_click_does(self):
		"""With differences checked it takes over that many; with none it notes the defaults of today as seen, after
		which every difference left counts as the user's own. Each form of a mapping words its button so and tells the
		server that the user decided, whatever was checked."""
		label = re.search(
			r"\nfunction take_over_label\(version\) \{\n(?P<body>.*?)\n\}\n", self.dialog, re.DOTALL
		)
		self.assertIsNotNone(label)
		texts = {
			"Take Over 1 Difference": "1 Unterschied übernehmen",
			"Take Over {0} Differences": "{0} Unterschiede übernehmen",
			"Take Over None and Note the Defaults {0} as Seen": (
				"Keinen übernehmen und die Vorgaben {0} als gesehen vermerken"
			),
		}
		self.assertEqual(set(TRANSLATED_LITERAL.findall(label["body"])), set(texts))
		german = translations()
		self.assertEqual({text: german.get(text) for text in texts}, texts)
		for form in FORMS:
			script = form.read_text(encoding="utf-8")
			with self.subTest(form=form.name):
				self.assertIn("apply_label: take_over_label(comparison.version),", script)
				self.assertIn('frm.call("update_from_defaults", { chosen, acknowledge: 1 })', script)


class MappingFileFilesTest(TestCase):
	"""Zuordnung exportieren and Zuordnung importieren: the browser saves the file, an upload stays private, and every
	message reads in German."""

	def setUp(self):
		self.source = (FOLDER / "vat_return_mapping.py").read_text(encoding="utf-8")
		self.script = (FOLDER / "vat_return_mapping.js").read_text(encoding="utf-8")

	def test_every_message_of_the_file_reads_in_german(self):
		german = translations()
		values = {
			node.targets[0].id: node.value
			for node in ast.parse(self.source).body
			if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
		}
		file_messages = {ast.literal_eval(values[name.id]) for name in values["FILE_MESSAGES"].elts}
		self.assertEqual(len(file_messages), 7)
		self.assertEqual(sorted((file_messages | set(transfer.MESSAGES)) - german.keys()), [])
		self.assertEqual(german["Export Mapping"], "Zuordnung exportieren")
		self.assertEqual(german["Import Mapping"], "Zuordnung importieren")

	def test_the_export_is_saved_by_the_browser_under_its_name(self):
		export = re.search(
			r"\nfunction export_mapping\(frm\) \{\n(?P<body>.*?)\n\}\n", self.script, re.DOTALL
		)
		self.assertIsNotNone(export)
		for part in ("new Blob([file.content]", "link.download = file.file_name;", "frm.reload_doc();"):
			with self.subTest(part=part):
				self.assertIn(part, export["body"])

	def test_an_upload_stays_private_and_the_file_browser_stays_closed(self):
		upload = re.search(
			r"\nfunction upload_mapping_file\(frm, dialog\) \{\n(?P<body>.*?)\n\}\n", self.script, re.DOTALL
		)
		self.assertIsNotNone(upload)
		for part in (
			"docname: frm.doc.name,",
			"allow_toggle_private: false,",
			"allow_web_link: false,",
			"disable_file_browser: true,",
			'allowed_file_types: [".json"]',
		):
			with self.subTest(part=part):
				self.assertIn(part, upload["body"])
		self.assertNotIn("make_attachments_public", upload["body"])


def definition(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def fields_of(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in definition(name)["fields"]}


class AnnualRowsFilesTest(TestCase):
	"""What the annual return reads of the mapping: the annual field and paragraph of a rule, and the rows of the
	accounts only the annual return reads, „Zuordnung nur für die Umsatzsteuererklärung“."""

	def setUp(self):
		self.script = (FOLDER / "vat_return_mapping.js").read_text(encoding="utf-8")

	def test_a_rule_names_its_annual_field_and_paragraph_by_choice(self):
		rule = fields_of("vat_return_mapping_rule")
		for name in CHOICE_FIELDS:
			with self.subTest(field=name):
				self.assertEqual(rule[name]["fieldtype"], "Data")
				self.assertFalse(rule[name].get("reqd"))
		self.assertEqual(definition("vat_return_mapping_rule")["field_order"][-2:], list(CHOICE_FIELDS))

	def test_a_row_for_the_annual_return_only_names_account_field_side_and_paragraph(self):
		annual = definition("vat_return_annual_rule")
		self.assertEqual(
			(annual["name"], annual["istable"], annual["module"]), ("VAT Return Annual Rule", 1, "Steuerbote")
		)
		self.assertEqual(annual["field_order"], ["account", "account_number", *ANNUAL_RULE_FIELDS])
		fields = fields_of("vat_return_annual_rule")
		self.assertEqual((fields["account"]["fieldtype"], fields["account"]["options"]), ("Link", "Account"))
		self.assertEqual(fields["account_number"]["fetch_from"], "account.account_number")
		self.assertEqual(fields["side"]["options"].split("\n"), ["credit", "debit"])
		self.assertEqual(
			{name for name, field in fields.items() if field.get("reqd")}, {"account", "annual_field", "side"}
		)

	def test_the_mapping_holds_the_rows_for_the_annual_return_only_after_its_watched_accounts(self):
		mapping = definition("vat_return_mapping")
		self.assertEqual(mapping["field_order"][-2:], ["watched", "annual_rules"])
		table = fields_of("vat_return_mapping")["annual_rules"]
		self.assertEqual((table["fieldtype"], table["options"]), ("Table", "VAT Return Annual Rule"))

	def test_the_form_offers_the_accounts_of_the_company_and_vorgaben_laden_replaces_the_rows_too(self):
		self.assertIn('for (const table of ["rules", "watched", "annual_rules"])', self.script)
		self.assertIn('["rules", "checks", "watched", "annual_rules"].some(', self.script)

	def test_the_rows_for_the_annual_return_read_in_german(self):
		german = translations()
		self.assertEqual(german["VAT Return Annual Rule"], "Zuordnung nur für die Umsatzsteuererklärung")
		self.assertEqual(
			german["Rules for the Annual Return Only"], "Zuordnungen nur für die Umsatzsteuererklärung"
		)
		self.assertEqual(german["Annual Return Field"], "Feld der Umsatzsteuererklärung")
		self.assertEqual(german["Paragraph of the Exemption"], "Paragraf der Steuerbefreiung")
		messages = set(TRANSLATED_LITERAL.findall(self.script)) | set(
			TRANSLATED_LITERAL.findall((FOLDER / "vat_return_mapping.py").read_text(encoding="utf-8"))
		)
		self.assertEqual(sorted(messages - german.keys()), [])

	def test_every_message_of_the_split_reads_in_german(self):
		"""Saving shows what the core of the annual return refuses (steuerbote/ustjahr/split.py)."""
		self.assertEqual(sorted(set(split.MESSAGES) - translations().keys()), [])
