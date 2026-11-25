"""The files of the Körperschaftsteuer- and the Gewerbesteuererklärung on the site, read without a bench: the fields their
controllers name, the form scripts, the print formats, the report Ertragsteuer-Kontennachweis and the German of the
texts of the controllers, the sources, the forms and the report."""

import ast
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.steuerbote.doctype.corporate_income_tax_return import test_bridge as corporate
from steuerbote.steuerbote.doctype.corporate_income_tax_return.test_income_tax_files import (
	APP,
	DOCTYPES,
	FRAMEWORK_LABELS,
	GEWST,
	KST,
	MODULE,
	PLACEHOLDER,
	fields_of,
	gewst_computation,
	read_json,
	translations,
)
from steuerbote.steuerbote.report.ertragsteuer_kontennachweis import attribution, test_attribution

SOURCES = APP / "income_tax_sources.py"
REPORT = MODULE / "report" / "ertragsteuer_kontennachweis"
PRINT_FORMATS = MODULE / "print_format"
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
"""The texts the pieces of the annual documents read from the form script of a return."""
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
CLASS_ATTRIBUTE = re.compile(r'\bclass="([^"]*)"')
CLASS_SELECTOR = re.compile(r"\.(-?[A-Za-z_][\w-]*)")


def controller(name: str) -> Path:
	return DOCTYPES / name / f"{name}.py"


def script(name: str) -> str:
	return (DOCTYPES / name / f"{name}.js").read_text(encoding="utf-8")


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


class ControllerFilesTest(TestCase):
	def test_the_corporate_income_tax_return_has_every_field_its_controller_names(self):
		fields = fields_of(KST)
		computed = constant(controller(KST), "CALCULATED_FIELDS", "CorporateIncomeTaxReturn")
		names = {
			*computed,
			*constant(controller(KST), "INPUT_FIELDS"),
			*constant(controller(KST), "INPUT_TABLES"),
			"lines",
			"provisions_entry",
			"provisional",
			"vorgang",
		}
		self.assertEqual(sorted(names - set(fields)), [])
		self.assertEqual(set(computed), set(corporate.compute().values))
		for fieldname in (*computed, "provisions_entry", "provisional", "vorgang"):
			with self.subTest(field=fieldname):
				self.assertEqual(fields[fieldname].get("read_only"), 1)
		for fieldname in (
			*constant(controller(KST), "INPUT_FIELDS"),
			*constant(controller(KST), "INPUT_TABLES"),
		):
			with self.subTest(field=fieldname):
				self.assertFalse(fields[fieldname].get("read_only"))

	def test_the_trade_tax_return_has_every_field_its_controller_names(self):
		fields = fields_of(GEWST)
		cls = "TradeTaxReturn"
		computed = constant(controller(GEWST), "CALCULATED_FIELDS", cls)
		tables = constant(controller(GEWST), "CALCULATED_TABLES", cls)
		names = {
			*computed,
			*tables,
			*constant(controller(GEWST), "INPUT_FIELDS"),
			"lines",
			"provisional",
			"vorgang",
		}
		self.assertEqual(sorted(names - set(fields)), [])
		self.assertEqual(set(computed), set(gewst_computation().values))
		for fieldname in (*computed, *tables, "provisional", "vorgang"):
			with self.subTest(field=fieldname):
				self.assertEqual(fields[fieldname].get("read_only"), 1)
		lines = fields["lines"]
		self.assertEqual((lines.get("cannot_add_rows"), lines.get("cannot_delete_rows")), (1, 1))

	def test_the_gewerbesteuererklaerung_takes_the_receipts_with_the_columns_of_their_table(self):
		receipt = ast.parse(controller(GEWST).read_text(encoding="utf-8"))
		(copied,) = (
			node for node in receipt.body if isinstance(node, ast.FunctionDef) and node.name == "_receipt"
		)
		(keys,) = (node for node in ast.walk(copied) if isinstance(node, ast.Dict))
		self.assertEqual(
			sorted({key.value for key in keys.keys} - set(fields_of("corporate_income_tax_return_donation"))),
			[],
		)

	def test_a_save_fills_the_columns_of_the_holding_results_that_the_form_shows_read_only(self):
		fields = fields_of("corporate_income_tax_return_holding_result")
		for fieldname in constant(controller(KST), "HOLDING_COLUMNS"):
			with self.subTest(field=fieldname):
				self.assertEqual(fields[fieldname]["read_only"], 1)

	def test_the_returns_show_their_elster_transmissions(self):
		for name, label in ((KST, "Corporate Income Tax Return"), (GEWST, "Trade Tax Return")):
			with self.subTest(doctype=name):
				source = (DOCTYPES / name / f"{name}_dashboard.py").read_text(encoding="utf-8")
				self.assertIn(f'return dashboard("{label}")', source)


class FormScriptFilesTest(TestCase):
	def test_include_the_transmission_before_the_pieces_of_the_annual_documents(self):
		for name in (KST, GEWST):
			source = script(name)
			with self.subTest(doctype=name):
				self.assertEqual(
					re.findall(r'\{% include "([^"]+)" %\}', source),
					["steuerbote/public/js/elster_transmission.js", "steuerbote/public/js/annual_filing.js"],
				)
				self.assertIn("annual_filing_setup(frm);", source)
				self.assertIn(f"annual_filing_refresh(frm, {name}_texts());", source)
				self.assertEqual(set(re.findall(r"^\t\t(\w+):", source, re.MULTILINE)), FORM_TEXTS)

	def test_say_that_mein_elster_imports_neither_return(self):
		for name, erklaerung in ((KST, "Körperschaftsteuererklärung"), (GEWST, "Gewerbesteuererklärung")):
			with self.subTest(doctype=name):
				self.assertIn(f"Mein ELSTER imports no {erklaerung}", script(name))
				self.assertIn("as Mein ELSTER takes no file of it", script(name))

	def test_the_koerperschaftsteuererklaerung_proposes_its_provisions(self):
		source = script(KST)
		self.assertIn('frm.add_custom_button(__("Propose Provisions")', source)
		self.assertIn('frm.call("propose_provisions")', source)
		self.assertIn('frappe.set_route("Form", "Journal Entry", r.message)', source)
		self.assertIn(
			'@frappe.whitelist(methods=["POST"])\n\t@guards.on_stored("write")\n\tdef propose_provisions(self)',
			controller(KST).read_text(encoding="utf-8"),
		)

	def test_the_koerperschaftsteuererklaerung_names_its_e_bilanz_of_the_jahresabschluss_of_its_company_and_year(
		self,
	):
		field = fields_of(KST)["electronic_balance_sheet"]
		self.assertEqual((field["fieldtype"], field["options"]), ("Link", "Electronic Balance Sheet"))
		self.assertFalse(field.get("read_only"))
		self.assertIn("electronic_balance_sheet", constant(controller(KST), "INPUT_FIELDS"))
		source = script(KST)
		self.assertIn('frm.set_query("electronic_balance_sheet"', source)
		for condition in (
			"company: frm.doc.company",
			"year: frm.doc.year",
			'statement_type: "Jahresabschluss"',
			'docstatus: ["!=", 2]',
		):
			with self.subTest(condition=condition):
				self.assertIn(condition, source)

	def test_the_gewerbesteuererklaerung_offers_the_koerperschaftsteuererklaerungen_of_its_company_and_year(
		self,
	):
		source = script(GEWST)
		self.assertIn('frm.set_query("corporate_income_tax_return"', source)
		self.assertIn(
			'filters: { company: frm.doc.company, year: frm.doc.year, docstatus: ["!=", 2] }', source
		)


class PrintFormatFilesTest(TestCase):
	FORMATS = (
		("körperschaftsteuererklärung", "Körperschaftsteuererklärung", "Corporate Income Tax Return", KST),
		("gewerbesteuererklärung", "Gewerbesteuererklärung", "Trade Tax Return", GEWST),
	)

	def files(self, directory: str) -> tuple[dict, str]:
		folder = PRINT_FORMATS / directory
		return read_json(folder / f"{directory}.json"), (folder / f"{directory}.html").read_text(
			encoding="utf-8"
		)

	def test_are_standard_jinja_formats_of_the_returns_on_a4(self):
		for directory, name, doctype, _ in self.FORMATS:
			record, _template = self.files(directory)
			with self.subTest(format=name):
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
						"name": name,
						"doc_type": doctype,
						"print_format_type": "Jinja",
						"standard": "Yes",
						"module": "Steuerbote",
						"custom_format": 0,
						"paper_size": "A4",
					},
				)

	def test_build_on_the_parts_of_the_annual_documents(self):
		for directory, name, _, _ in self.FORMATS:
			_record, template = self.files(directory)
			includes = re.findall(
				r'\{% include "steuerbote/templates/includes/annual_filing/(\w+)\.html" %\}', template
			)
			corrections = ["corrections"] if directory == "körperschaftsteuererklärung" else []
			with self.subTest(format=name):
				self.assertEqual(includes, ["head", *corrections, "findings", "remarks", "footer"])
				self.assertIn('{% include "steuerbote/templates/includes/print/style.html" %}', template)
				self.assertIn("{%- set annual = doc.annual_print() -%}", template)
				self.assertIn("{%- set form = doc.income_tax_print() -%}", template)
				self.assertIn(f"<h1>{name} {{{{ doc.year }}}}</h1>", template)

	def test_mark_the_forms_of_a_provisional_year(self):
		for directory, name, _, _ in self.FORMATS:
			_record, template = self.files(directory)
			with self.subTest(format=name):
				self.assertIn("{%- if form.provisional %}", template)
				self.assertIn("vorläufig (Jahresdokumentation {{ form.documentation_year }})", template)

	def test_print_the_sections_and_rows_the_layout_gives(self):
		for directory, name, _, doctype in self.FORMATS:
			_record, template = self.files(directory)
			with self.subTest(format=name):
				self.assertEqual(set(re.findall(r"\bsection\.(\w+)", template)), {"title", "rows"})
				read = set(re.findall(r"\brow\.(\w+)", template))
				municipality = {"municipality", "ags", "hebesatz_source"} if doctype == GEWST else set()
				self.assertEqual(read, {"line", "label", "instance", "value", *municipality})
				self.assertEqual(sorted(municipality - set(fields_of("trade_tax_return_municipality"))), [])
				printed = set(re.findall(r"\bdoc\.(\w+)", template)) - {
					"annual_print",
					"income_tax_print",
					"get_formatted",
				}
				self.assertEqual(
					sorted(printed - set(fields_of(doctype)) - {"is_correction", "year", "company"}), []
				)

	def test_print_in_black_and_grey(self):
		for directory, name, _, _ in self.FORMATS:
			record, template = self.files(directory)
			for text in (template, record["css"]):
				for colour in HEX_COLOUR.findall(text):
					with self.subTest(format=name, colour=colour):
						channels = colour if len(colour) == 3 else (colour[0:2], colour[2:4], colour[4:6])
						self.assertEqual(len(set(channels)), 1)
			self.assertNotIn("<img", template)

	def test_keep_to_classes_of_their_own_and_style_each_they_use(self):
		for directory, name, _, _ in self.FORMATS:
			record, template = self.files(directory)
			self.assertEqual(record["css"], "")
			used = {item for value in CLASS_ATTRIBUTE.findall(template) for item in value.split()}
			style = PRINT_STYLE.read_text(encoding="utf-8")
			styled = set(CLASS_SELECTOR.findall(re.sub(r"\d+\.\d+", "", style)))
			with self.subTest(format=name):
				self.assertEqual(sorted(item for item in used if not item.startswith("sb-")), [])
				self.assertEqual(sorted(used - styled), [])


class ReportFilesTest(TestCase):
	def test_is_a_standard_script_report_of_the_koerperschaftsteuererklaerung(self):
		report = read_json(REPORT / "ertragsteuer_kontennachweis.json")
		self.assertEqual(
			{
				key: report[key]
				for key in ("name", "report_name", "report_type", "ref_doctype", "is_standard", "module")
			},
			{
				"name": "Ertragsteuer-Kontennachweis",
				"report_name": "Ertragsteuer-Kontennachweis",
				"report_type": "Script Report",
				"ref_doctype": "Corporate Income Tax Return",
				"is_standard": "Yes",
				"module": "Steuerbote",
			},
		)
		self.assertEqual(
			{row["role"] for row in report["roles"]}, {"Accounts Manager", "Accounts User", "System Manager"}
		)

	def test_the_filters_of_the_script_are_those_the_report_reads(self):
		source = (REPORT / "ertragsteuer_kontennachweis.js").read_text(encoding="utf-8")
		self.assertEqual(
			re.findall(r'fieldname: "(\w+)"', source),
			list(constant(REPORT / "ertragsteuer_kontennachweis.py", "FILTERS")),
		)

	def test_shows_a_tree_of_lines_accounts_and_vouchers(self):
		source = (REPORT / "ertragsteuer_kontennachweis.js").read_text(encoding="utf-8")
		for part in ("tree: true,", 'name_field: "node",', 'parent_field: "parent_node",'):
			with self.subTest(part=part):
				self.assertIn(part, source)
		columns = set(
			re.findall(
				r'"fieldname": "(\w+)"',
				(REPORT / "ertragsteuer_kontennachweis.py").read_text(encoding="utf-8"),
			)
		)
		rows = attribution.report_rows(test_attribution.LEDGER, test_attribution.MAPPING, {}, {})
		self.assertEqual(
			sorted(
				{key for row in rows for key in row} - columns - {"node", "parent_node", "indent", "bold"}
			),
			[],
		)

	def test_shows_its_texts_as_they_read(self):
		"""Frappe writes a Data cell of a report into the page as HTML; the formatter escapes each before Frappe
		formats it."""
		source = (REPORT / "ertragsteuer_kontennachweis.js").read_text(encoding="utf-8")
		self.assertIn('column.fieldtype === "Data" ? frappe.utils.escape_html(value) : value', source)
		data_columns = set(
			re.findall(
				r'\{"fieldname": "(\w+)", "label": _\("[^"]*"\), "fieldtype": "Data"',
				(REPORT / "ertragsteuer_kontennachweis.py").read_text(encoding="utf-8"),
			)
		)
		self.assertEqual(data_columns, {"line", "feldkennung", "label"})


def texts_of_the_sources() -> set[str]:
	texts = set()
	for path in (
		controller(KST),
		controller(GEWST),
		DOCTYPES / KST / f"{KST}.js",
		DOCTYPES / GEWST / f"{GEWST}.js",
		SOURCES,
		REPORT / "ertragsteuer_kontennachweis.py",
		REPORT / "ertragsteuer_kontennachweis.js",
	):
		texts.update(TRANSLATED_LITERAL.findall(path.read_text(encoding="utf-8")))
	return texts


class SiteTranslationsFilesTest(TestCase):
	def test_the_sources_are_read(self):
		for text in (
			"Propose Provisions",
			"Steuerbote has no forms of the Gewerbesteuer for {0} yet.",
			"Ledger Amount",
		):
			with self.subTest(text=text):
				self.assertIn(text, texts_of_the_sources())

	def test_every_text_of_the_controllers_the_sources_the_forms_and_the_report_is_translated(self):
		self.assertEqual(sorted(texts_of_the_sources() - set(translations()) - FRAMEWORK_LABELS), [])

	def test_the_translations_keep_the_placeholders(self):
		german = translations()
		for text in texts_of_the_sources() - FRAMEWORK_LABELS:
			with self.subTest(text=text):
				self.assertCountEqual(PLACEHOLDER.findall(german[text]), PLACEHOLDER.findall(text))

	def test_the_action_reads_as_the_contract_names_it(self):
		self.assertEqual(translations()["Propose Provisions"], "Rückstellungen vorschlagen")
