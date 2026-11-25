"""The files of the E-Bilanz on the site, read without a bench: the fields its controller names, the form script, the
print format, the report E-Bilanz Positionen and the German of the texts of the controller, the sources, the form and
the report."""

import ast
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.steuerbote.doctype.electronic_balance_sheet import bridge, layout
from steuerbote.steuerbote.doctype.electronic_balance_sheet.test_bridge import ebilanz
from steuerbote.steuerbote.doctype.electronic_balance_sheet.test_electronic_balance_sheet_files import (
	APP,
	DOCTYPES,
	FRAMEWORK_LABELS,
	MODULE,
	NAME,
	PLACEHOLDER,
	fields_of,
	read_json,
	translations,
)
from steuerbote.steuerbote.report.e_bilanz_positionen import rows as report_rows

CONTROLLER = DOCTYPES / NAME / f"{NAME}.py"
SCRIPT = DOCTYPES / NAME / f"{NAME}.js"
SOURCES = APP / "ebilanz_sources.py"
REPORT = MODULE / "report" / "e_bilanz_positionen"
PRINT_FORMAT = MODULE / "print_format" / "e_bilanz"
INCLUDES = APP / "templates" / "includes" / "annual_filing"
# The one stylesheet of every print format of the app.
PRINT_STYLE = APP / "templates" / "includes" / "print" / "style.html"
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
FORM_TEXTS = frozenset(
	{
		"unsaved",
		"send",
		"test_send",
		"sent",
		"running",
		"simulation",
		"berichtigung",
		"ready",
		"filed_outside_example",
	}
)
"""The texts the pieces of the annual documents read from the form script of a document."""
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
CLASS_ATTRIBUTE = re.compile(r'\bclass="([^"]*)"')
CLASS_SELECTOR = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
CLASS = "ElectronicBalanceSheet"


def constant(path: Path, name: str, cls: str | None = None) -> object:
	"""The value of a constant of a module or of a class in it, read from its source."""
	body = ast.parse(path.read_text(encoding="utf-8")).body
	if cls is not None:
		(found,) = (node for node in body if isinstance(node, ast.ClassDef) and node.name == cls)
		body = found.body
	(value,) = (
		node.value
		for node in body
		if isinstance(node, ast.Assign) and [getattr(target, "id", None) for target in node.targets] == [name]
	)
	return ast.literal_eval(value)


def script() -> str:
	return SCRIPT.read_text(encoding="utf-8")


class ControllerFilesTest(TestCase):
	def test_has_every_field_its_controller_names(self):
		fields = fields_of(NAME)
		computed = constant(CONTROLLER, "CALCULATED_FIELDS", CLASS)
		tables = (constant(CONTROLLER, "ACCOUNTS"),)
		self.assertIn("CALCULATED_TABLES = (ACCOUNTS,)", CONTROLLER.read_text(encoding="utf-8"))
		names = {
			*computed,
			*tables,
			*constant(CONTROLLER, "KEY_FIELDS", CLASS),
			*bridge.INPUT_FIELDS,
			constant(CONTROLLER, "LINES", CLASS),
			constant(CONTROLLER, "FIXED_ASSETS"),
			constant(CONTROLLER, "TRANSFERS"),
			"stichtag",
		}
		self.assertEqual(sorted(names - set(fields)), [])
		for fieldname in (*computed, *tables, "stichtag"):
			with self.subTest(field=fieldname):
				self.assertEqual(fields[fieldname].get("read_only"), 1)
		for fieldname in bridge.INPUT_FIELDS:
			with self.subTest(field=fieldname):
				self.assertFalse(fields[fieldname].get("read_only"))

	def test_berechnen_fills_every_calculated_field(self):
		computed = set(constant(CONTROLLER, "CALCULATED_FIELDS", CLASS))
		self.assertEqual(
			computed,
			{
				*bridge.totals(ebilanz()),
				"bvv_previous_equity",
				"bvv_founding_contribution",
				"bvv_booked_contributions",
				"first_fiscal_year",
				"annual_accounts",
			},
		)

	def test_names_the_jahresabschluss_whose_handelsbilanz_berechnen_compares_it_with(self):
		field = fields_of(NAME)["annual_accounts"]
		self.assertEqual(
			(field["fieldtype"], field["options"], field.get("read_only")), ("Link", "Annual Accounts", 1)
		)
		self.assertEqual(field["depends_on"], "eval:doc.statement_type!=='Eröffnungsbilanz'")
		self.assertIn("comparison.findings(", CONTROLLER.read_text(encoding="utf-8"))

	def test_the_jahresabschluss_lists_the_e_bilanzen_that_name_it(self):
		source = (DOCTYPES / "annual_accounts" / "annual_accounts_dashboard.py").read_text(encoding="utf-8")
		self.assertIn('"fieldname": "annual_accounts"', source)
		self.assertIn('"items": ["Electronic Balance Sheet"]', source)

	def test_the_key_is_the_company_the_year_and_the_bilanzart(self):
		self.assertEqual(constant(CONTROLLER, "KEY_FIELDS", CLASS), ("company", "year", "statement_type"))

	def test_without_the_hersteller_id_the_filing_is_noted_as_made_outside(self):
		source = CONTROLLER.read_text(encoding="utf-8")
		self.assertIn("FILED_OUTSIDE = (OTHER_WAY,)", source)
		self.assertIn(
			'@frappe.whitelist(methods=["POST"])\n\t@guards.on_stored("write")\n\tdef export_xbrl(self) -> str:',
			source,
		)
		self.assertIn("eric_datenart.bilanz(self.taxonomy_version)", source)
		self.assertIn("simulated_bilanz.register_taxonomy(version,", source)

	def test_shows_its_elster_transmissions(self):
		source = (DOCTYPES / NAME / f"{NAME}_dashboard.py").read_text(encoding="utf-8")
		self.assertIn('return dashboard("Electronic Balance Sheet")', source)


class FormScriptFilesTest(TestCase):
	def test_includes_the_transmission_before_the_pieces_of_the_annual_documents(self):
		source = script()
		self.assertEqual(
			re.findall(r'\{% include "([^"]+)" %\}', source),
			["steuerbote/public/js/elster_transmission.js", "steuerbote/public/js/annual_filing.js"],
		)
		self.assertIn("annual_filing_setup(frm);", source)
		self.assertIn(f"annual_filing_refresh(frm, {NAME}_texts());", source)
		self.assertEqual(set(re.findall(r"^\t\t(\w+):", source, re.MULTILINE)), FORM_TEXTS)

	def test_says_that_mein_elster_takes_no_e_bilanz(self):
		self.assertIn("Mein ELSTER takes no E-Bilanz", script())
		self.assertIn("Mark as Filed Outside", script())

	def test_exports_the_xbrl_file_of_a_saved_e_bilanz(self):
		source = script()
		self.assertIn('frm.add_custom_button(__("Export XBRL")', source)
		self.assertIn('frm.call("export_xbrl")', source)
		self.assertIn("frm.doc.__onload.electronic_balance_sheet", source)

	def test_a_new_e_bilanz_takes_the_bilanzierungsstandard_of_the_settings(self):
		source = script()
		self.assertIn('.get_value("Annual Filing Settings", frm.doc.company, "accounting_standard")', source)
		self.assertIn('frm.set_value("accounting_standard", standard)', source)


class PrintFormatFilesTest(TestCase):
	def files(self) -> tuple[dict, str]:
		return read_json(PRINT_FORMAT / "e_bilanz.json"), (PRINT_FORMAT / "e_bilanz.html").read_text(
			encoding="utf-8"
		)

	def test_is_a_standard_jinja_format_of_the_e_bilanz_on_a4(self):
		record, _template = self.files()
		self.assertEqual(
			{
				key: record[key]
				for key in (
					"name",
					"doc_type",
					"print_format_type",
					"standard",
					"module",
					"custom_format",
					"paper_size",
				)
			},
			{
				"name": "E-Bilanz",
				"doc_type": "Electronic Balance Sheet",
				"print_format_type": "Jinja",
				"standard": "Yes",
				"module": "Steuerbote",
				"custom_format": 0,
				"paper_size": "A4",
			},
		)

	def test_builds_on_the_parts_of_the_annual_documents(self):
		_record, template = self.files()
		self.assertEqual(
			re.findall(
				r'\{% include "steuerbote/templates/includes/annual_filing/(\w+)\.html" %\}', template
			),
			["head", "corrections", "findings", "remarks", "footer"],
		)
		self.assertIn('{% include "steuerbote/templates/includes/print/style.html" %}', template)
		self.assertIn("{%- set annual = doc.annual_print() -%}", template)
		self.assertIn("{%- set form = doc.e_bilanz_print() -%}", template)
		self.assertIn("<h1>E-Bilanz {{ doc.year }}</h1>", template)

	def test_prints_the_sections_the_layout_gives(self):
		_record, template = self.files()
		sections = layout.print_sections([])
		self.assertEqual(sorted(set(re.findall(r"\bform\.(\w+)", template)) - set(sections)), [])
		self.assertEqual(
			sorted(
				set(re.findall(r"\bform\.anlagenspiegel\.(\w+)", template)) - set(sections["anlagenspiegel"])
			),
			[],
		)
		printed = set(re.findall(r"\bdoc\.(\w+)", template)) - {"annual_print", "e_bilanz_print"}
		self.assertEqual(sorted(printed - set(fields_of(NAME))), [])
		for heading in (
			"<h2>Bilanz</h2>",
			"<h2>Gewinn- und Verlustrechnung (Gesamtkostenverfahren)</h2>",
			"<h2>Steuerlicher Betriebsvermögensvergleich</h2>",
			"<h2>Anlagenspiegel (brutto)</h2>",
			"<h2>Kontennachweis</h2>",
			"<h2>Überleitungsrechnung</h2>",
		):
			with self.subTest(heading=heading):
				self.assertIn(heading, template)

	def test_prints_in_black_and_grey(self):
		record, template = self.files()
		for text in (template, record["css"]):
			for colour in HEX_COLOUR.findall(text):
				with self.subTest(colour=colour):
					channels = colour if len(colour) == 3 else (colour[0:2], colour[2:4], colour[4:6])
					self.assertEqual(len(set(channels)), 1)
		self.assertNotIn("<img", template)

	def test_keeps_to_classes_of_its_own_and_styles_each_it_uses(self):
		record, template = self.files()
		self.assertEqual(record["css"], "")
		used = {item for value in CLASS_ATTRIBUTE.findall(template) for item in value.split()}
		style = PRINT_STYLE.read_text(encoding="utf-8")
		styled = set(CLASS_SELECTOR.findall(re.sub(r"\d+\.\d+", "", style)))
		self.assertEqual(sorted(item for item in used if not item.startswith("sb-")), [])
		self.assertEqual(sorted(used - styled), [])


class ReportFilesTest(TestCase):
	def test_is_a_standard_script_report_of_the_e_bilanz(self):
		report = read_json(REPORT / "e_bilanz_positionen.json")
		self.assertEqual(
			{
				key: report[key]
				for key in ("name", "report_name", "report_type", "ref_doctype", "is_standard", "module")
			},
			{
				"name": "E-Bilanz Positionen",
				"report_name": "E-Bilanz Positionen",
				"report_type": "Script Report",
				"ref_doctype": "Electronic Balance Sheet",
				"is_standard": "Yes",
				"module": "Steuerbote",
			},
		)
		self.assertEqual(
			{row["role"] for row in report["roles"]}, {"Accounts Manager", "Accounts User", "System Manager"}
		)

	def test_the_filters_of_the_script_are_those_the_report_reads(self):
		source = (REPORT / "e_bilanz_positionen.js").read_text(encoding="utf-8")
		self.assertEqual(
			re.findall(r'fieldname: "(\w+)"', source),
			list(constant(REPORT / "e_bilanz_positionen.py", "FILTERS")),
		)
		self.assertEqual(re.findall(r'\{ value: "([^"]+)"', source), options_of_the_bilanzart())

	def test_shows_a_tree_of_positions_and_accounts(self):
		source = (REPORT / "e_bilanz_positionen.js").read_text(encoding="utf-8")
		for part in ("tree: true,", 'name_field: "key",', 'parent_field: "parent_key",'):
			with self.subTest(part=part):
				self.assertIn(part, source)
		columns = set(
			re.findall(
				r'"fieldname": "(\w+)"', (REPORT / "e_bilanz_positionen.py").read_text(encoding="utf-8")
			)
		)
		found = ebilanz()
		rows = report_rows.report_rows(bridge.position_rows(found), bridge.account_rows(found))
		self.assertEqual(
			sorted({key for row in rows for key in row} - columns - {"parent_key", "indent", "bold"}), []
		)

	def test_shows_its_texts_as_they_read(self):
		"""Frappe writes a Data cell of a report into the page as HTML; the formatter escapes each before Frappe
		formats it."""
		source = (REPORT / "e_bilanz_positionen.js").read_text(encoding="utf-8")
		self.assertIn(
			"default_formatter(text ? frappe.utils.escape_html(value) : value, row, column, data)", source
		)


def options_of_the_bilanzart() -> list[str]:
	return fields_of(NAME)["statement_type"]["options"].split("\n")


def texts_of_the_sources() -> set[str]:
	texts = set()
	for path in (
		CONTROLLER,
		SCRIPT,
		SOURCES,
		REPORT / "e_bilanz_positionen.py",
		REPORT / "e_bilanz_positionen.js",
	):
		texts.update(TRANSLATED_LITERAL.findall(path.read_text(encoding="utf-8")))
	return texts


class SiteTranslationsFilesTest(TestCase):
	def test_the_sources_are_read(self):
		for text in ("Export XBRL", "Save the E-Bilanz before exporting it.", "Kind of Balance Sheet"):
			with self.subTest(text=text):
				self.assertIn(text, texts_of_the_sources())

	def test_every_text_of_the_controller_the_sources_the_form_and_the_report_is_translated(self):
		self.assertEqual(sorted(texts_of_the_sources() - set(translations()) - FRAMEWORK_LABELS), [])

	def test_the_translations_keep_the_placeholders(self):
		german = translations()
		for text in texts_of_the_sources() - FRAMEWORK_LABELS:
			with self.subTest(text=text):
				self.assertCountEqual(PLACEHOLDER.findall(german[text]), PLACEHOLDER.findall(text))

	def test_the_actions_read_as_the_contract_names_them(self):
		german = translations()
		self.assertEqual(german["Export XBRL"], "XBRL exportieren")
		self.assertEqual(german["Mark as Filed Outside"], "Als außerhalb abgegeben vermerken")
