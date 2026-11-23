"""The Income Tax Mapping, read from its files without a bench: its tables offer the categories, classes and levels of
the core, the methods its form calls are whitelisted for POST, every text reads in German, its step of Steuerbote
einrichten is the one of the hook, and its dialogs escape what the site holds."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote import hooks
from steuerbote.income_tax_mapping_sync import RULE_FIELDS
from steuerbote.kst.categories import CATEGORIES, Category, TradingClass
from steuerbote.mappings import transfer
from steuerbote.mappings.diff import Change, Origin
from steuerbote.setup.steps import Step
from steuerbote.ustva.mapping import WatchLevel

APP = Path(__file__).resolve().parents[3]
DOCTYPES = APP / "steuerbote" / "doctype"
FOLDER = DOCTYPES / "income_tax_mapping"
VAT_FOLDER = DOCTYPES / "vat_return_mapping"
TRANSLATIONS = APP / "translations" / "de.csv"
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
# Labels Frappe translates itself, and the names of the charts, which read the same in every language.
FRAMEWORK_LABELS = frozenset({"Account", "Category", "Company"})
CHART_NAMES = frozenset({"SKR03", "SKR04", "Eigener Kontenrahmen"})
# The categories whose option reads otherwise than their label in the core: a trading account takes its class beside
# the category, and the investment funds share their option with the trading class of the same name.
OWN_OPTION_LABELS = {
	Category.TRADING_UNCLASSIFIED: "Handelsergebnis",
	Category.FUNDS: "Investmentfonds (InvStG)",
}


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def definition(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def field(doctype: str, fieldname: str) -> dict:
	(found,) = (field for field in definition(doctype)["fields"] if field["fieldname"] == fieldname)
	return found


def options(doctype: str, fieldname: str) -> list[str]:
	return field(doctype, fieldname)["options"].split("\n")


def assignments(path: Path) -> dict[str, ast.expr]:
	return {
		node.targets[0].id: node.value
		for node in ast.parse(path.read_text(encoding="utf-8")).body
		if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
	}


class TablesTest(TestCase):
	def test_the_mapping_is_one_per_company_with_its_chart_its_defaults_and_its_tables(self):
		mapping = definition("income_tax_mapping")
		self.assertEqual(
			(mapping["name"], mapping["autoname"], mapping["module"], mapping["track_changes"]),
			("Income Tax Mapping", "field:company", "Steuerbote", 1),
		)
		self.assertEqual(
			mapping["field_order"],
			["company", "chart", "defaults_version", "defaults_rows", "rules", "watched"],
		)
		self.assertEqual(options("income_tax_mapping", "chart"), ["SKR03", "SKR04", "Eigener Kontenrahmen"])
		self.assertEqual(
			(
				field("income_tax_mapping", "rules")["options"],
				field("income_tax_mapping", "watched")["options"],
			),
			("Income Tax Mapping Rule", "Income Tax Watched Account"),
		)
		self.assertEqual(field("income_tax_mapping", "defaults_rows")["hidden"], 1)
		self.assertEqual(
			{permission["role"] for permission in mapping["permissions"]},
			{"System Manager", "Accounts Manager", "Accounts User"},
		)

	def test_a_rule_offers_the_categories_and_classes_of_the_core_a_class_only_for_a_trading_account(self):
		self.assertEqual(options("income_tax_mapping_rule", "category"), ["", *(c.value for c in Category)])
		self.assertEqual(
			options("income_tax_mapping_rule", "trading_class"), ["", *(t.value for t in TradingClass)]
		)
		self.assertEqual(field("income_tax_mapping_rule", "category")["reqd"], 1)
		self.assertEqual(
			field("income_tax_mapping_rule", "trading_class")["depends_on"],
			f'eval:doc.category == "{Category.TRADING_UNCLASSIFIED.value}"',
		)
		self.assertEqual(
			[name for name in definition("income_tax_mapping_rule")["field_order"] if name in RULE_FIELDS],
			list(RULE_FIELDS),
		)

	def test_a_watched_account_offers_the_levels_of_the_core_and_blocks_unless_set(self):
		level = field("income_tax_watched_account", "level")
		self.assertEqual(level["options"].split("\n"), [level.value for level in WatchLevel])
		self.assertEqual(level["default"], WatchLevel.BLOCKING.value)

	def test_the_accounts_of_both_tables_are_ledger_accounts_with_their_numbers(self):
		for doctype in ("income_tax_mapping_rule", "income_tax_watched_account"):
			with self.subTest(doctype=doctype):
				self.assertEqual(definition(doctype)["istable"], 1)
				self.assertEqual(field(doctype, "account")["options"], "Account")
				self.assertEqual(field(doctype, "account_number")["fetch_from"], "account.account_number")


class FormFilesTest(TestCase):
	def setUp(self):
		self.script = (FOLDER / "income_tax_mapping.js").read_text(encoding="utf-8")
		self.source = (FOLDER / "income_tax_mapping.py").read_text(encoding="utf-8")

	def test_the_methods_the_form_calls_are_whitelisted_for_post(self):
		methods = sorted(set(re.findall(r'frm\.call\("(\w+)"', self.script)))
		self.assertEqual(
			methods,
			[
				"compare_with_defaults",
				"compare_with_file",
				"export_mapping",
				"import_file",
				"load_defaults",
				"update_from_defaults",
			],
		)
		for method in methods:
			with self.subTest(method=method):
				self.assertRegex(self.source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')

	def test_the_form_includes_the_dialog_of_the_differences(self):
		self.assertTrue(
			self.script.startswith('{% include "steuerbote/public/js/mapping_differences.js" %}\n')
		)

	def test_the_dialog_of_the_missing_accounts_escapes_their_numbers_and_labels(self):
		dialog = re.search(
			r"\nfunction show_missing_accounts\(missing\) \{\n(?P<body>.*?)\n\}\n", self.script, re.DOTALL
		)
		self.assertIsNotNone(dialog)
		body = dialog["body"]
		self.assertIn("const escape = frappe.utils.escape_html;", body)
		for value in ("account.account_number", "account.label"):
			with self.subTest(value=value):
				shown = re.findall(rf"\$\{{[^}}]*{re.escape(value)}[^}}]*\}}", body)
				self.assertTrue(shown)
				self.assertTrue(all("escape" in expression for expression in shown), shown)

	def test_a_category_without_class_clears_the_class_of_its_row(self):
		handler = re.search(
			r'frappe\.ui\.form\.on\("Income Tax Mapping Rule", \{\n(?P<body>.*?)\n\}\);',
			self.script,
			re.DOTALL,
		)
		self.assertIsNotNone(handler)
		self.assertIn('frappe.model.set_value(cdt, cdn, "trading_class", "")', handler["body"])
		self.assertIn(f'const TRADING_CATEGORY = "{Category.TRADING_UNCLASSIFIED.value}";', self.script)

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

	def test_the_export_is_saved_by_the_browser_under_its_name(self):
		export = re.search(
			r"\nfunction export_mapping\(frm\) \{\n(?P<body>.*?)\n\}\n", self.script, re.DOTALL
		)
		self.assertIsNotNone(export)
		for part in ("new Blob([file.content]", "link.download = file.file_name;", "frm.reload_doc();"):
			with self.subTest(part=part):
				self.assertIn(part, export["body"])


class TranslationsTest(TestCase):
	def test_every_text_of_the_mapping_reads_in_german(self):
		german = translations()
		texts: set[str] = set()
		for name in ("income_tax_mapping", "income_tax_mapping_rule", "income_tax_watched_account"):
			doctype = definition(name)
			texts.add(doctype["name"])
			for field_ in doctype["fields"]:
				texts.update(field_[key] for key in ("label", "description") if field_.get(key))
				if field_["fieldtype"] == "Select":
					texts.update(option for option in field_["options"].split("\n") if option)
		texts.update(
			TRANSLATED_LITERAL.findall((FOLDER / "income_tax_mapping.js").read_text(encoding="utf-8"))
		)
		texts.update(
			TRANSLATED_LITERAL.findall((FOLDER / "income_tax_mapping.py").read_text(encoding="utf-8"))
		)
		values = assignments(FOLDER / "income_tax_mapping.py")
		texts.update(ast.literal_eval(values["FIELD_LABELS"]).values())
		texts.add(ast.literal_eval(values["INVALID_MAPPING"]))
		texts.update(transfer.MESSAGES)
		self.assertEqual(sorted(texts - german.keys() - FRAMEWORK_LABELS - CHART_NAMES), [])
		self.assertEqual(german["Income Tax Mapping"], "Kontenzuordnung Ertragsteuern")
		self.assertEqual(german["Load Defaults"], "Vorgaben laden")

	def test_the_categories_read_as_the_core_names_them(self):
		german = translations()
		for category in Category:
			with self.subTest(category=category):
				self.assertEqual(
					german[category.value], OWN_OPTION_LABELS.get(category, CATEGORIES[category].label)
				)
		self.assertEqual(
			{trading_class.value: german[trading_class.value] for trading_class in TradingClass},
			{
				"shares": "Anteile (§ 8b KStG)",
				"derivatives": "Termingeschäfte (§ 15 Abs. 4 Satz 3 EStG)",
				"funds": "Investmentfonds (InvStG)",
				"taxable": "Voll steuerpflichtig",
			},
		)

	def test_the_dialog_shares_its_changes_and_origins_with_the_vat_return_mapping(self):
		source = (FOLDER / "income_tax_mapping.py").read_text(encoding="utf-8")
		self.assertIn("CHANGES,", source)
		self.assertIn("ORIGINS,", source)
		vat = assignments(VAT_FOLDER / "vat_return_mapping.py")
		german = translations()
		for name, members in (("CHANGES", Change), ("ORIGINS", Origin)):
			labels = {
				key.attr: value.value for key, value in zip(vat[name].keys, vat[name].values, strict=True)
			}
			with self.subTest(name=name):
				self.assertEqual(set(labels), {member.name for member in members})
				self.assertEqual(sorted(set(labels.values()) - german.keys()), [])


class SetupStepTest(TestCase):
	def test_the_hook_runs_the_step_of_the_mapping_after_the_steps_of_the_voranmeldung(self):
		(entry,) = (entry for entry in hooks.steuerbote_setup_steps if entry["key"] == "income_tax_mapping")
		step = Step.from_hook(entry)
		self.assertEqual(
			(step.key, step.label, step.order, step.run, step.needs),
			(
				"income_tax_mapping",
				"Income Tax Mapping",
				40,
				"steuerbote.steuerbote.doctype.income_tax_mapping.setup.run",
				(),
			),
		)
		self.assertTrue((FOLDER / "setup.py").is_file())
		self.assertRegex(
			(FOLDER / "setup.py").read_text(encoding="utf-8"), r"\ndef run\(context: SetupContext\)"
		)

	def test_every_note_of_the_step_reads_in_german(self):
		german = translations()
		values = assignments(FOLDER / "setup.py")
		messages = {ast.literal_eval(values[name.id]) for name in values["MESSAGES"].elts}
		self.assertEqual(len(messages), 7)
		self.assertEqual(sorted(messages - german.keys()), [])
