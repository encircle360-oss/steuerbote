"""The files of the Annual Accounts, read without a bench: its DocTypes with the fields of an annual document and the
columns of the base, the rows the bridge writes and the options it reads, the fields the controller names, the form
script, the print format „Jahresabschluss“ with its parts, and the German of their texts and of the messages of the
bridge."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.hgb.notes import Answer
from steuerbote.hgb.schemes import Level
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.statement import RemainingTerm
from steuerbote.hgb.tests import companies
from steuerbote.jahresmeldung.lifecycle import ACCOUNTS, field_problems
from steuerbote.steuerbote.doctype.annual_accounts import bridge

APP = Path(__file__).resolve().parents[3]
MODULE = APP / "steuerbote"
DOCTYPES = MODULE / "doctype"
HERE = DOCTYPES / "annual_accounts"
PRINT_FORMAT = MODULE / "print_format" / "jahresabschluss"
INCLUDES = APP / "templates" / "includes"
OWN_INCLUDES = INCLUDES / "annual_accounts"
TRANSLATIONS = APP / "translations" / "de.csv"
PARENT = "annual_accounts"
CHILDREN = (
	"annual_accounts_line",
	"annual_accounts_note",
	"annual_accounts_signatory",
	"annual_accounts_prior_entry",
)
ALL = (PARENT, *CHILDREN)
SOURCES = (
	HERE / "annual_accounts.py",
	HERE / "annual_accounts.js",
	HERE / "xbrl_export.py",
	APP / "annual_accounts_sources.py",
	APP / "headcount.py",
)
PLACEHOLDER = re.compile(r"\{\d*\}")
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
CLASS_ATTRIBUTE = re.compile(r'\bclass="([^"]*)"')
CLASS_SELECTOR = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
JINJA_TAG = re.compile(r"{%.*?%}|{{.*?}}|{#.*?#}", re.DOTALL)
# Labels Frappe and ERPNext translate themselves (frappe/locale/de.po and erpnext/locale/de.po of version 16); the app
# keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{
		"Amended From",
		"Amount",
		"Channel",
		"Code",
		"Description",
		"Due Date",
		"Fees",
		"Fiscal Year",
		"From Date",
	}
	| {"Function", "Receipt", "Remarks", "Requirement", "Series", "Source", "Status", "Text", "To Date"}
)
# Terms that read the same in German.
UNTRANSLATED = frozenset(
	{"Angabe", "Angaben", "Arbeitnehmer", "Bilanzsumme", "Eigenkapital", "Einstellung", "Ergebnisverwendung"}
	| {
		"Feststellung",
		"Firma",
		"Gewinnvortrag/Verlustvortrag",
		"In Liquidation",
		"Jahresergebnis",
		"Offenlegung",
	}
	| {"Sitz", "Transferticket", "Umsatzerlöse", "Vortrag auf neue Rechnung", "Übermittlung", "{0}"}
)
# The keys of the Jahresabschluss, the classes, the schemes and the answers are German already, and the states of the
# lifecycle are shown as they are.
UNTRANSLATED_SELECTS = frozenset(
	{"naming_series", "status", "filed_via", "statement", "level", "answer", "remaining_term", "presentation"}
	| {
		"prior_size_class",
		"size_class_computed",
		"size_class_override",
		"size_class",
		"disclosure_mode",
		"channel",
	}
)
WHITELISTED = (
	"make_disclosure_preview",
	"make_xbrl",
	"record_transmission",
	"record_publication",
	"make_appropriation_entry",
)


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def definition(name: str) -> dict:
	return read_json(DOCTYPES / name / f"{name}.json")


def fields_of(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in definition(name)["fields"]}


def options_of(name: str, fieldname: str) -> list[str]:
	return fields_of(name)[fieldname]["options"].split("\n")


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def controller() -> ast.Module:
	return ast.parse((HERE / "annual_accounts.py").read_text(encoding="utf-8"))


def constant(name: str, cls: str | None = None) -> object:
	"""The value of a constant of the controller or of its class, read from its source."""
	body = controller().body
	if cls is not None:
		(found,) = (node for node in body if isinstance(node, ast.ClassDef) and node.name == cls)
		body = found.body
	(value,) = (
		node.value
		for node in body
		if isinstance(node, ast.Assign) and [getattr(target, "id", None) for target in node.targets] == [name]
	)
	if isinstance(value, ast.Call):
		(value,) = value.args
	return ast.literal_eval(value)


def method(name: str) -> ast.FunctionDef:
	(found,) = (
		node for node in ast.walk(controller()) if isinstance(node, ast.FunctionDef) and node.name == name
	)
	return found


def dict_keys(function: ast.FunctionDef, target: str | None = None) -> set[str]:
	"""The literal keys of the dict a function assigns to ``target``, or of the one it returns."""
	for node in ast.walk(function):
		if target and isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == target:
			found = node.value
			break
		if not target and isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
			found = node.value
			break
	return {key.value for key in found.keys if isinstance(key, ast.Constant)}


def stored_rows() -> list[dict]:
	found = bridge.statements(
		2026, SizeClass.KLEIN, companies.KLEIN_2026, parents=companies.PARENTS, prior=companies.KLEIN_2025
	)
	return bridge.line_rows(found, companies.PARENTS)


class DocTypeFilesTest(TestCase):
	def test_has_the_fields_of_an_annual_document_that_goes_to_no_authority_through_steuerbote(self):
		self.assertEqual(field_problems(definition(PARENT), ACCOUNTS, transmits=False), [])

	def test_is_submittable_and_numbered_by_the_year_of_the_fiscal_year(self):
		record = definition(PARENT)
		self.assertEqual(
			(record["name"], record["autoname"], record["is_submittable"], record["track_changes"]),
			("Annual Accounts", "naming_series:", 1, 1),
		)
		series = fields_of(PARENT)["naming_series"]
		self.assertEqual((series["options"], series["default"]), ("JA-.{year}.-.#####",) * 2)

	def test_its_permissions_are_those_of_the_vat_return(self):
		self.assertEqual(definition(PARENT)["permissions"], definition("vat_return")["permissions"])

	def test_the_field_order_names_every_field_once(self):
		for name in ALL:
			with self.subTest(doctype=name):
				record = definition(name)
				self.assertEqual(record["field_order"], [field["fieldname"] for field in record["fields"]])
				self.assertEqual(len(set(record["field_order"])), len(record["field_order"]))
				self.assertEqual(record["module"], "Steuerbote")

	def test_the_tables_take_their_child_doctypes(self):
		tables = {
			"lines": "Annual Accounts Line",
			"notes": "Annual Accounts Note",
			"signatories": "Annual Accounts Signatory",
			"prior_entries": "Annual Accounts Prior Entry",
			"findings": "Annual Filing Finding",
		}
		fields = fields_of(PARENT)
		self.assertEqual({table: fields[table]["options"] for table in tables}, tables)
		for name in CHILDREN:
			with self.subTest(doctype=name):
				self.assertEqual(definition(name)["istable"], 1)

	def test_the_lines_and_the_angaben_come_from_berechnen(self):
		fields = fields_of(PARENT)
		for table in ("lines", "notes"):
			with self.subTest(table=table):
				self.assertEqual(
					(fields[table].get("cannot_add_rows"), fields[table].get("cannot_delete_rows")), (1, 1)
				)

	def test_the_lines_hold_the_columns_of_the_base_and_take_only_the_correction(self):
		fields = fields_of("annual_accounts_line")
		columns = bridge.LINE_COLUMNS
		needed = {
			columns.key,
			*columns.amounts,
			*columns.described,
			columns.correction,
			columns.reason,
			columns.reported,
			columns.manual,
		}
		self.assertEqual(sorted(needed - set(fields)), [])
		editable = sorted(
			fieldname
			for fieldname, field in fields.items()
			if not field.get("read_only") and field["fieldtype"] != "Column Break"
		)
		self.assertEqual(editable, ["correction", "correction_reason"])
		for fieldname in editable:
			with self.subTest(field=fieldname):
				self.assertEqual(fields[fieldname]["read_only_depends_on"], "eval:!doc.takes_correction")

	def test_the_tables_hold_the_rows_the_bridge_writes(self):
		for child, rows in (
			("annual_accounts_line", stored_rows()),
			(
				"annual_accounts_note",
				bridge.note_rows(bridge.catalogue_of(SizeClass.KLEIN, equity_zero=True), []),
			),
		):
			with self.subTest(table=child):
				self.assertTrue(rows)
				self.assertEqual(sorted({key for row in rows for key in row} - set(fields_of(child))), [])
		signatory = {"signatory_name", "function", "place", "signed_on"}
		self.assertEqual(sorted(signatory - set(fields_of("annual_accounts_signatory"))), [])

	def test_the_options_are_those_the_bridge_reads(self):
		sizes = ["", *(stored.value for stored in bridge.SIZE_CLASSES)]
		for fieldname in ("prior_size_class", "size_class_computed", "size_class_override", "size_class"):
			with self.subTest(field=fieldname):
				self.assertEqual(options_of(PARENT, fieldname), sizes)
		for name, fieldname, options in (
			(PARENT, "presentation", ["", *bridge.PRESENTATIONS]),
			(PARENT, "disclosure_mode", ["", *(mode.value for mode in bridge.DisclosureMode)]),
			(PARENT, "channel", ["", *constant("CHANNELS")]),
			("annual_accounts_line", "statement", [side.value for side in bridge.Statement]),
			("annual_accounts_line", "level", [*(level.value for level in Level), bridge.VERMERK]),
			("annual_accounts_note", "answer", ["", *(answer.value for answer in Answer)]),
			("annual_accounts_prior_entry", "remaining_term", ["", *(term.value for term in RemainingTerm)]),
		):
			with self.subTest(doctype=name, field=fieldname):
				self.assertEqual(options_of(name, fieldname), options)

	def test_the_grids_show_at_most_ten_columns(self):
		for name in CHILDREN:
			with self.subTest(doctype=name):
				listed = [field for field in definition(name)["fields"] if field.get("in_list_view")]
				self.assertLessEqual(sum(field.get("columns", 0) for field in listed), 10)

	def test_the_money_takes_the_currency_of_the_company(self):
		for name in ALL:
			for field in definition(name)["fields"]:
				if field["fieldtype"] == "Currency":
					with self.subTest(doctype=name, field=field["fieldname"]):
						self.assertEqual(field["options"], "Company:company:default_currency")

	def test_no_field_changes_after_the_feststellung(self):
		for name in ALL:
			for field in definition(name)["fields"]:
				with self.subTest(doctype=name, field=field["fieldname"]):
					self.assertFalse(field.get("allow_on_submit"))


class ControllerFilesTest(TestCase):
	def test_has_every_field_its_controller_names(self):
		fields = fields_of(PARENT)
		calculated = constant("CALCULATED_FIELDS", "AnnualAccounts")
		recorded = constant("RECORDED_FIELDS")
		entered = (*constant("INPUT_FIELDS"), *constant("INPUT_TABLES"), *constant("ADOPTION_FIELDS"))
		self.assertEqual(sorted({*calculated, *recorded, *entered} - set(fields)), [])
		for fieldname in (*calculated, *recorded):
			with self.subTest(field=fieldname):
				self.assertEqual(fields[fieldname].get("read_only"), 1)
		for fieldname in entered:
			with self.subTest(field=fieldname):
				self.assertFalse(fields[fieldname].get("read_only"))
		for fieldname in recorded:
			with self.subTest(field=fieldname):
				self.assertEqual(fields[fieldname].get("no_copy"), 1)

	def test_the_tables_berechnen_reads_name_columns_of_their_rows(self):
		for table, columns in constant("INPUT_TABLES").items():
			child = fields_of(PARENT)[table]["options"].lower().replace(" ", "_")
			with self.subTest(table=table):
				self.assertEqual(sorted(set(columns) - set(fields_of(child))), [])

	def test_berechnen_sets_the_calculated_fields_and_the_offenlegung(self):
		keys = dict_keys(method("compute"), "calculated")
		register = set(bridge.register_values("", {}))
		self.assertEqual(
			keys | register, {*constant("CALCULATED_FIELDS", "AnnualAccounts"), "disclosure_mode"}
		)

	def test_the_steps_after_berechnen_are_whitelisted_for_post(self):
		source = (HERE / "annual_accounts.py").read_text(encoding="utf-8")
		for name in WHITELISTED:
			with self.subTest(method=name):
				self.assertRegex(source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {name}\(')

	def test_the_print_reads_what_annual_accounts_print_gives(self):
		given = dict_keys(method("annual_accounts_print"))
		read = set()
		for path in (PRINT_FORMAT / "jahresabschluss.html", *OWN_INCLUDES.glob("*.html")):
			read |= set(re.findall(r"\baccounts\.(\w+)", path.read_text(encoding="utf-8")))
		self.assertEqual(sorted(read - given - {"annual_accounts_print"}), [])
		self.assertEqual(sorted(given - read), [])


class FormScriptFilesTest(TestCase):
	def setUp(self):
		self.source = (HERE / "annual_accounts.js").read_text(encoding="utf-8")

	def test_includes_the_pieces_of_the_annual_documents_and_no_transmission(self):
		self.assertEqual(
			re.findall(r'\{% include "([^"]+)" %\}', self.source), ["steuerbote/public/js/annual_filing.js"]
		)
		self.assertIn("annual_filing_setup(frm);", self.source)
		self.assertIn("annual_filing_refresh(frm, annual_accounts_texts());", self.source)
		self.assertEqual(set(re.findall(r"^\t\t(\w+):", self.source, re.MULTILINE)), {"ready"})

	def test_calls_each_step_after_berechnen(self):
		for name in WHITELISTED:
			with self.subTest(method=name):
				self.assertIn(f'frm.call("{name}"', self.source)

	def test_the_dialogs_send_what_the_steps_take(self):
		for name, dialog in (
			("record_transmission", "annual_accounts_transmission"),
			("record_publication", "annual_accounts_publication"),
		):
			parameters = [argument.arg for argument in method(name).args.args[1:]]
			body = self.source.split(f"function {dialog}(frm) {{", 1)[1].split("\n}\n", 1)[0]
			with self.subTest(method=name):
				self.assertEqual(sorted(re.findall(r'fieldname: "(\w+)"', body)), sorted(parameters))

	def test_the_dialogs_attach_their_files_to_the_jahresabschluss(self):
		self.assertEqual(self.source.count('fieldtype: "Attach"'), 2)
		self.assertIn("const upload = { doctype: frm.doctype, docname: frm.doc.name };", self.source)
		self.assertIn("options: { doctype: frm.doctype, docname: frm.doc.name },", self.source)

	def test_the_channels_are_those_of_the_controller(self):
		self.assertIn(
			"const ANNUAL_ACCOUNTS_CHANNELS = ["
			+ ", ".join(f'"{channel}"' for channel in constant("CHANNELS"))
			+ "];",
			self.source,
		)


class PrintFormatFilesTest(TestCase):
	def setUp(self):
		self.record = read_json(PRINT_FORMAT / "jahresabschluss.json")
		self.template = (PRINT_FORMAT / "jahresabschluss.html").read_text(encoding="utf-8")
		self.parts = {path.stem: path.read_text(encoding="utf-8") for path in OWN_INCLUDES.glob("*.html")}

	def test_is_a_standard_jinja_format_of_the_annual_accounts_on_a4(self):
		self.assertEqual(
			{
				key: self.record[key]
				for key in (
					"name",
					"doc_type",
					"print_format_type",
					"standard",
					"module",
					"custom_format",
					"paper_size",
					"default_print_language",
				)
			},
			{
				"name": "Jahresabschluss",
				"doc_type": "Annual Accounts",
				"print_format_type": "Jinja",
				"standard": "Yes",
				"module": "Steuerbote",
				"custom_format": 0,
				"paper_size": "A4",
				"default_print_language": "de",
			},
		)

	def test_builds_on_the_parts_of_the_annual_documents_and_its_own(self):
		includes = re.findall(
			r'\{% include "steuerbote/templates/includes/([\w/]+)\.html" %\}', self.template
		)
		self.assertEqual(
			includes,
			[
				"print/style",
				"annual_accounts/offenlegung",
				"annual_filing/head",
				"annual_accounts/bilanz",
				"annual_accounts/guv",
				"annual_accounts/angaben",
				"annual_accounts/signatures",
				"annual_accounts/upload",
				"annual_filing/corrections",
				"annual_filing/findings",
				"annual_filing/remarks",
				"annual_filing/footer",
			],
		)
		self.assertEqual(
			re.findall(
				r'\{% include "steuerbote/templates/includes/annual_accounts/(\w+)\.html" %\}',
				self.parts["offenlegung"],
			),
			["bilanz", "angaben", "signatures", "upload"],
		)
		self.assertIn("{%- set annual = doc.annual_print() -%}", self.template)
		self.assertIn("{%- set accounts = doc.annual_accounts_print() -%}", self.template)

	def test_the_vorschau_prints_what_becomes_visible_and_no_guv(self):
		self.assertIn("{%- if accounts.preview %}", self.template)
		self.assertIn("{%- set shown_notes = accounts.published_notes %}", self.parts["offenlegung"])
		self.assertNotIn("guv", self.parts["offenlegung"])
		self.assertIn("{{ visible.notice | e }}", self.parts["offenlegung"])

	def test_signs_with_gez_and_the_date_and_names_the_feststellung(self):
		self.assertIn("{%- for line in accounts.signatures %}", self.parts["signatures"])
		self.assertIn("Festgestellt am {{ day(doc.adopted_on) }}.", self.parts["signatures"])

	def test_marks_the_fields_of_the_web_form_as_unverified(self):
		self.assertIn("{%- if not upload.web_form.verified %}", self.parts["upload"])
		self.assertIn("Nicht geprüft:", self.parts["upload"])

	def test_prints_the_fields_of_the_annual_accounts(self):
		printed = set()
		for text in (self.template, *self.parts.values()):
			printed |= set(re.findall(r"\bdoc\.(\w+)", text))
		printed -= {"annual_print", "annual_accounts_print"}
		self.assertEqual(sorted(printed - set(fields_of(PARENT))), [])

	def test_prints_in_black_and_grey_without_images(self):
		for text in (self.template, self.record["css"], *self.parts.values()):
			for colour in HEX_COLOUR.findall(text):
				with self.subTest(colour=colour):
					channels = colour if len(colour) == 3 else (colour[0:2], colour[2:4], colour[4:6])
					self.assertEqual(len(set(channels)), 1)
			self.assertNotIn("<img", text)

	def test_renders_without_a_browser(self):
		"""PlutoPrint of Frappe 16 renders a page without scripts and CSS grid (frappe/utils/pdf_generator/pluto.py)."""
		for text in (self.template, self.record["css"], *self.parts.values()):
			self.assertNotIn("<script", JINJA_TAG.sub("", text))
			self.assertNotRegex(text, r"display\W+(inline-)?grid\b")

	def test_keeps_to_classes_of_its_own_and_styles_each_it_uses(self):
		used = set()
		for text in (self.template, *self.parts.values()):
			for value in CLASS_ATTRIBUTE.findall(JINJA_TAG.sub(" ", text)):
				used.update(value.split())
		style = (INCLUDES / "print" / "style.html").read_text(encoding="utf-8")
		styled = set(CLASS_SELECTOR.findall(re.sub(r"\d+\.\d+", "", style)))
		self.assertEqual(sorted(item for item in used if not item.startswith("sb-")), [])
		self.assertEqual(sorted(used - styled), [])


def texts_of_the_doctypes() -> set[str]:
	texts = set()
	for name in ALL:
		record = definition(name)
		texts.update(text for text in (record["name"], record.get("description")) if text)
		for field in record["fields"]:
			texts.update(field[key] for key in ("label", "description") if field.get(key))
			if field["fieldtype"] == "Select" and field["fieldname"] not in UNTRANSLATED_SELECTS:
				texts.update(option for option in field["options"].split("\n") if option)
	return texts


def texts_of_the_sources() -> set[str]:
	texts = set()
	for path in SOURCES:
		texts.update(TRANSLATED_LITERAL.findall(path.read_text(encoding="utf-8")))
	return texts


class TranslationsFilesTest(TestCase):
	def test_the_sources_are_read(self):
		for text, found in (
			("Annual Accounts Signatory", texts_of_the_doctypes()),
			("Hinterlegung Box Ticked", texts_of_the_doctypes()),
			("Record Übermittlung", texts_of_the_sources()),
			("{0} is not festgestellt, so it is not transmitted.", texts_of_the_sources()),
		):
			with self.subTest(text=text):
				self.assertIn(text, found)

	def test_every_text_of_the_doctypes_is_translated(self):
		missing = texts_of_the_doctypes() - set(translations()) - FRAMEWORK_LABELS - UNTRANSLATED
		self.assertEqual(sorted(missing), [])

	def test_every_message_of_the_bridge_is_translated(self):
		self.assertEqual(sorted(set(bridge.MESSAGES) - set(translations()) - UNTRANSLATED), [])

	def test_every_text_of_the_controller_the_form_and_the_sources_is_translated(self):
		self.assertEqual(
			sorted(texts_of_the_sources() - set(translations()) - FRAMEWORK_LABELS - UNTRANSLATED), []
		)

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & set(translations())), [])

	def test_the_translations_keep_the_placeholders(self):
		german = translations()
		for text in (set(bridge.MESSAGES) | texts_of_the_sources()) - FRAMEWORK_LABELS - UNTRANSLATED:
			with self.subTest(text=text):
				self.assertCountEqual(PLACEHOLDER.findall(german[text]), PLACEHOLDER.findall(text))

	def test_the_document_and_its_steps_read_as_the_law_and_the_register_name_them(self):
		german = translations()
		for text, expected in (
			("Annual Accounts", "Jahresabschluss"),
			("Preview of the Offenlegung", "Vorschau der Offenlegung"),
			("XBRL for the Unternehmensregister", "XBRL für das Unternehmensregister"),
			("Record Übermittlung", "Übermittlung festhalten"),
			("Record Einstellung", "Einstellung festhalten"),
			("Post Ergebnisverwendung", "Ergebnisverwendung buchen"),
		):
			with self.subTest(text=text):
				self.assertEqual(german[text], expected)
