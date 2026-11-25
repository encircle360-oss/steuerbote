"""The files of the base of the annual documents, read without a bench: the child DocType Annual Filing Finding, the
methods the forms call and the German of every text."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.jahresmeldung import acknowledgements, findings
from steuerbote.jahresmeldung.findings import Severity
from steuerbote.jahresmeldung.lifecycle import ACCOUNTS, FILING, standard_fields

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote"
BASE = MODULE / "annual_filing.py"
FINDING = MODULE / "doctype" / "annual_filing_finding" / "annual_filing_finding.json"
TRANSLATIONS = APP / "translations" / "de.csv"
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
# Labels Frappe translates itself; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset({"Code", "Discard", "Kind", "Message", "Reference", "Remarks"})
# The labels of the standard fields that Frappe and ERPNext translate themselves (frappe/locale/de.po and
# erpnext/locale/de.po of version 16), and Transferticket, which is German already.
STANDARD_LABELS_OF_THE_FRAMEWORK = frozenset(
	{"Due Date", "Fiscal Year", "From Date", "Remarks", "Status", "To Date", "Transferticket"}
)


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
		columns = [*row, *acknowledgements.FIELDS]
		self.assertEqual(self.definition["field_order"], columns)
		self.assertEqual(list(self.fields), columns)

	def test_names_art_sperrt_code_nachricht_and_referenz(self):
		self.assertEqual(
			{name: (field["fieldtype"], field["label"]) for name, field in self.fields.items()},
			{
				"severity": ("Select", "Kind"),
				"blocking": ("Check", "Blocking"),
				"code": ("Data", "Code"),
				"text": ("Small Text", "Message"),
				"reference": ("Data", "Reference"),
				"acknowledgeable": ("Check", "Can Be Acknowledged"),
				"acknowledged": ("Check", "Acknowledged"),
				"acknowledgement_reason": ("Small Text", "Reason for Filing Nonetheless"),
				"acknowledged_by": ("Link", "Acknowledged By"),
				"acknowledged_on": ("Datetime", "Acknowledged On"),
			},
		)

	def test_the_kinds_are_the_severities_of_the_core(self):
		self.assertEqual(
			self.fields["severity"]["options"].split("\n"), [severity.value for severity in Severity]
		)

	def test_only_steuerbote_writes_a_finding_and_the_grid_shows_what_it_says_and_whether_it_is_acknowledged(
		self,
	):
		"""Berechnen writes a finding and acknowledge_finding its acknowledgement; the form edits none of it."""
		for name, field in self.fields.items():
			with self.subTest(field=name):
				self.assertEqual(field.get("read_only"), 1)
		listed = [name for name, field in self.fields.items() if field.get("in_list_view")]
		self.assertEqual(listed, ["severity", "code", "text", "reference", "acknowledged"])
		self.assertLessEqual(sum(self.fields[name]["columns"] for name in listed), 10)


class BaseFilesTest(TestCase):
	def setUp(self):
		self.source = BASE.read_text(encoding="utf-8")

	def test_the_methods_a_form_calls_are_whitelisted_for_post(self):
		for method in ("calculate", "make_correction", "mark_filed_outside", "acknowledge_finding"):
			with self.subTest(method=method):
				self.assertRegex(self.source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')

	def test_every_text_of_the_base_is_translated(self):
		texts = set(TRANSLATED_LITERAL.findall(self.source)) | definition_texts(read_json(FINDING))
		self.assertIn("Calculate {0} before filing it.", texts)
		self.assertEqual(sorted(texts - translated() - FRAMEWORK_LABELS), [])

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & translated()), [])

	def test_every_label_of_the_standard_fields_is_translated(self):
		labels = {
			field.label
			for lifecycle in (FILING, ACCOUNTS)
			for field in standard_fields(lifecycle, "Annual VAT Return", transmits=True)
		}
		self.assertIn("Correction", labels)
		self.assertEqual(sorted(labels - translated() - STANDARD_LABELS_OF_THE_FRAMEWORK), [])


SCRIPT = APP / "public" / "js" / "annual_filing.js"
TRANSMISSION_SCRIPT = APP / "public" / "js" / "elster_transmission.js"
SCRIPT_LITERAL = re.compile(r"\b__\(\s*\"((?:[^\"\\]|\\.)*)\"")
# German terms that read the same in every language.
UNTRANSLATED = frozenset({"Transferticket"})


def parameters(source: str, method: str) -> list[str]:
	"""The parameters of a method of a class of a Python module, without self."""
	(function,) = (
		node
		for node in ast.walk(ast.parse(source))
		if isinstance(node, ast.FunctionDef) and node.name == method
	)
	return [argument.arg for argument in function.args.args[1:]]


class FormScriptFilesTest(TestCase):
	"""The pieces the forms of the annual documents share, which a form includes after elster_transmission.js when it
	goes to ELSTER."""

	def setUp(self):
		self.script = SCRIPT.read_text(encoding="utf-8")
		self.base = BASE.read_text(encoding="utf-8")

	def test_the_methods_the_script_calls_are_those_of_the_base_whitelisted_for_post(self):
		methods = set(re.findall(r'frm\.call\("(\w+)"', self.script))
		self.assertEqual(
			methods, {"calculate", "make_correction", "mark_filed_outside", "acknowledge_finding"}
		)
		for method in sorted(methods):
			with self.subTest(method=method):
				self.assertRegex(self.base, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')

	def test_the_note_of_a_filing_sends_what_the_base_takes(self):
		(sent,) = re.findall(r'frm\.call\("mark_filed_outside", \{([^}]*)\}', self.script)
		self.assertEqual(
			[argument.split(":")[0].strip() for argument in sent.split(",") if argument.strip()],
			parameters(self.base, "mark_filed_outside"),
		)

	def test_the_script_reads_the_state_the_base_hands_the_form(self):
		self.assertIn('self.set_onload("annual_filing", self.annual_state())', self.base)
		self.assertIn("frm.doc.__onload.annual_filing", self.script)
		for key in ("calculated", "filings", "filed_outside", "submitted_by_hand", "can_correct"):
			with self.subTest(key=key):
				self.assertIn(f'"{key}"', self.base)
				self.assertIn(f"state.{key}", self.script)

	def test_a_draft_that_goes_to_elster_is_filed_through_it_and_never_by_buchen_alone(self):
		self.assertIn("frm.show_submit_message = () => {};", self.script)
		self.assertIn("offer_buchen_only_for_an_accepted_send(frm);", self.script)

	def test_every_text_of_the_script_is_translated(self):
		texts = set(SCRIPT_LITERAL.findall(self.script))
		self.assertIn("Make Berichtigung", texts)
		self.assertEqual(sorted(texts - translated() - UNTRANSLATED - FRAMEWORK_LABELS), [])


class TransmissionScriptFilesTest(TestCase):
	def test_the_certificate_dialog_names_what_eric_prints_after_the_send(self):
		script = TRANSMISSION_SCRIPT.read_text(encoding="utf-8")
		self.assertIn("elster_state(frm).printout", script)
		self.assertEqual(
			sorted(set(SCRIPT_LITERAL.findall(script)) - translated() - UNTRANSLATED - FRAMEWORK_LABELS), []
		)


INCLUDES = APP / "templates" / "includes" / "annual_filing"
PARTS = ("style", "head", "corrections", "findings", "remarks", "footer")
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
CLASS_ATTRIBUTE = re.compile(r'\bclass="([^"]*)"')
CLASS_SELECTOR = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
# Frappe's print stylesheet styles bare classes such as .label (inline, 75 %, bold), so the includes name their classes
# with a prefix of their own, as the print formats of the app do.
PRINT_CLASS_PREFIX = "sb-"


def include(part: str) -> str:
	return (INCLUDES / f"{part}.html").read_text(encoding="utf-8")


class PrintIncludesFilesTest(TestCase):
	"""The shared parts of the print formats of the annual documents (contract of stage 3, 2.5): A4, black and grey,
	classes of their own, and the footer for the Steuerberatung and Mein ELSTER."""

	def setUp(self):
		self.style = include("style")
		self.parts = {part: include(part) for part in PARTS}

	def test_prints_on_a4_in_black_and_grey(self):
		self.assertIn("size: A4 portrait", self.style)
		for part, text in self.parts.items():
			for colour in HEX_COLOUR.findall(text):
				with self.subTest(part=part, colour=colour):
					channels = colour if len(colour) == 3 else (colour[0:2], colour[2:4], colour[4:6])
					self.assertEqual(len(set(channels)), 1)
			with self.subTest(part=part):
				self.assertNotIn("<img", text)
				self.assertNotRegex(text, r"\b(rgb|hsl)a?\(")

	def test_keeps_to_classes_of_its_own_and_styles_each_it_uses(self):
		used = {
			name
			for text in self.parts.values()
			for value in CLASS_ATTRIBUTE.findall(text)
			for name in value.split()
		}
		styled = set(CLASS_SELECTOR.findall(re.sub(r"\d+\.\d+", "", self.style)))
		self.assertNotIn("label", used | styled)
		self.assertEqual(
			sorted(name for name in used | styled if not name.startswith(PRINT_CLASS_PREFIX)), []
		)
		self.assertEqual(sorted(used - styled), [])

	def test_the_head_pairs_each_label_with_its_value(self):
		labels = re.findall(
			r'<tr><td class="sb-label">([^<{]+)</td><td class="sb-value">', self.parts["head"]
		)
		self.assertEqual(
			labels,
			[
				"Unternehmen",
				"Steuernummer",
				"Steuernummer im ELSTER-Format",
				"Jahr",
				"Geschäftsjahr",
				"Fällig am",
				"Beleg",
				"Berichtigung zu",
				"Abgegeben am",
			],
		)
		self.assertIn("head_rows", self.parts["head"])

	def test_the_footer_names_the_steuerberatung_and_mein_elster_but_for_the_e_bilanz(self):
		footer = self.parts["footer"]
		self.assertIn("Zum Abgleich mit der Steuerberatung oder zum Übertragen in Mein ELSTER.", footer)
		self.assertIn("Zum Abgleich mit der Steuerberatung.", footer)
		self.assertIn("Dieser Ausdruck ist keine Abgabe.", footer)
		self.assertIn("Dieser Ausdruck ist keine Offenlegung.", footer)

	def test_the_parts_read_only_what_the_base_hands_them(self):
		source = BASE.read_text(encoding="utf-8")
		(body,) = re.findall(r"def annual_print\(self\) -> dict\[str, Any\]:(.*?)\n\tdef ", source, re.DOTALL)
		provided = set(re.findall(r'"(\w+)":', body))
		for part, text in self.parts.items():
			with self.subTest(part=part):
				self.assertEqual(sorted(set(re.findall(r"\bannual\.(\w+)", text)) - provided), [])
				self.assertEqual(
					sorted(
						set(re.findall(r"\brow\.(\w+)", text))
						- provided
						- {"severity", "code", "text", "reference", "get_formatted"}
						- {"acknowledged", "acknowledgement_reason"}
					),
					[],
				)


# The annual documents of stage 3 by the names the contract of stage 3 fixed for them; their modules bring them.
ANNUAL_DOCUMENTS = (
	"Annual VAT Return",
	"Electronic Balance Sheet",
	"Corporate Income Tax Return",
	"Trade Tax Return",
	"Annual Accounts",
)
# What went to the tax authorities and the proof of the confirmations of USt-IdNrn., kept before stage 3.
FILINGS = (
	"VAT ID Confirmation",
	"Recapitulative Statement",
	"VAT Return Extension",
	"VAT Return",
	"ELSTER Transmission",
	"VAT Return Prior Filing",
)


def doctypes_of_the_app() -> set[str]:
	return {read_json(path)["name"] for path in (MODULE / "doctype").glob("*/*.json")}


class HooksFilesTest(TestCase):
	"""ERPNext's Delete Company Transactions leaves the DocTypes of company_data_to_be_ignored alone."""

	def setUp(self):
		from steuerbote import hooks

		self.kept = hooks.company_data_to_be_ignored

	def test_keeps_the_filings_and_the_annual_filing_settings(self):
		self.assertEqual(self.kept[: len(FILINGS) + 1], [*FILINGS, "Annual Filing Settings"])

	def test_keeps_each_annual_document_once_the_app_brings_its_doctype(self):
		self.assertEqual(
			self.kept[len(FILINGS) + 1 :],
			[name for name in ANNUAL_DOCUMENTS if name in doctypes_of_the_app()],
		)

	def test_names_no_doctype_the_app_does_not_bring(self):
		"""The record of the deletion links each name to its DocType and refuses one that does not exist."""
		self.assertEqual(sorted(set(self.kept) - doctypes_of_the_app()), [])


DOCS = APP.parent / "docs"
PAGE = DOCS / "jahresmeldungen.md"
ARCHITECTURE = DOCS / "architektur.md"
TRANSMISSION_DOCS = DOCS / "uebermittlung.md"
TRANSMISSION_DOCTYPE = MODULE / "doctype" / "elster_transmission"


def public_members(source: str, name: str) -> list[str]:
	"""The attributes and methods of a class of a Python module that do not start with an underscore."""
	(cls,) = (node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == name)
	members = []
	for node in cls.body:
		if isinstance(node, ast.FunctionDef):
			members.append(node.name)
		elif isinstance(node, ast.AnnAssign):
			members.append(node.target.id)
		elif isinstance(node, ast.Assign):
			members.extend(target.id for target in node.targets)
	return [member for member in members if not member.startswith("_")]


def documented(text: str) -> set[str]:
	"""The names a page writes as code outside its code blocks, a call such as `move_on(event)` by its name."""
	prose = re.sub(r"^```.*?^```$", "", text, flags=re.DOTALL | re.MULTILINE)
	return {re.sub(r"\(.*\)$", "", name) for name in re.findall(r"`([^`]+)`", prose)}


class DocsFilesTest(TestCase):
	"""docs/jahresmeldungen.md names what a module of an annual document builds on, and the architecture and the page
	on the transmission to ELSTER name the base and what it changed of the ELSTER Transmission."""

	def setUp(self):
		self.page = documented(PAGE.read_text(encoding="utf-8"))
		self.base = BASE.read_text(encoding="utf-8")

	def test_names_every_hook_attribute_and_method_of_the_base(self):
		members = public_members(self.base, "AnnualFiling")
		self.assertIn("compute", members)
		self.assertEqual(sorted(set(members) - self.page), [])

	def test_names_what_berechnen_of_a_module_returns(self):
		self.assertEqual(sorted({"Calculation", *public_members(self.base, "Calculation")} - self.page), [])

	def test_names_the_functions_and_texts_a_form_hands_the_script(self):
		scripts = SCRIPT.read_text(encoding="utf-8") + TRANSMISSION_SCRIPT.read_text(encoding="utf-8")
		texts = set(re.findall(r"\btexts\.(\w+)", scripts))
		self.assertTrue({"berichtigung", "send"} <= texts)
		self.assertEqual(sorted({"annual_filing_setup", "annual_filing_refresh", *texts} - self.page), [])

	def test_names_every_print_include_and_what_it_reads(self):
		(body,) = re.findall(
			r"def annual_print\(self\) -> dict\[str, Any\]:(.*?)\n\tdef ", self.base, re.DOTALL
		)
		read = {f"{part}.html" for part in PARTS} | set(re.findall(r'"(\w+)":', body)) | {"head_rows"}
		self.assertEqual(sorted(read - self.page), [])

	def test_the_architecture_names_the_base_and_links_its_page(self):
		text = ARCHITECTURE.read_text(encoding="utf-8")
		self.assertIn("| `steuerbote/steuerbote/annual_filing.py` |", text)
		self.assertIn("](jahresmeldungen.md)", text)

	def test_the_architecture_names_every_document_of_the_elster_transmission(self):
		source = (TRANSMISSION_DOCTYPE / "elster_transmission.py").read_text(encoding="utf-8")
		(assignment,) = (
			node
			for node in ast.parse(source).body
			if isinstance(node, ast.Assign) and [target.id for target in node.targets] == ["DOCUMENT_TYPES"]
		)
		document_types = [element.value for element in assignment.value.elts]
		self.assertIn("Electronic Balance Sheet", document_types)
		(row,) = (
			line
			for line in ARCHITECTURE.read_text(encoding="utf-8").splitlines()
			if line.startswith("| `document_type`, `document`, `company` |")
		)
		self.assertEqual(sorted(set(document_types) - documented(row)), [])

	def test_the_docs_name_the_printout_by_the_label_of_its_field(self):
		fields = read_json(TRANSMISSION_DOCTYPE / "elster_transmission.json")["fields"]
		(label,) = (field["label"] for field in fields if field["fieldname"] == "protocol_pdf")
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			german = dict(csv.reader(file))[label]
		for path in (ARCHITECTURE, TRANSMISSION_DOCS):
			with self.subTest(page=path.name):
				self.assertIn(german, path.read_text(encoding="utf-8"))
