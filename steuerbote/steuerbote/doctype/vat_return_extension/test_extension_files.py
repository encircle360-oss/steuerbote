"""The Dauerfristverlängerung read from its files without a bench: every text has a German translation in
translations/de.csv, the form never offers Buchen alone and transmits through the script it shares with the VAT
Return, and the print format keeps to the wording of form USt 1 H and to the style of the app."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.dauerfrist import Context, layout_for
from steuerbote.dauerfrist.form import MESSAGES as FORM_MESSAGES

APP = Path(__file__).resolve().parents[3]
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
FOLDER = DOCTYPES / "vat_return_extension"
CONTROLLER = FOLDER / "vat_return_extension.py"
SCRIPT = FOLDER / "vat_return_extension.js"
# The transmission through ERiC, in the browser and on the server, which the VAT Return shares.
SHARED_SCRIPT = APP / "public" / "js" / "elster_transmission.js"
TRANSMITTABLE = DOCTYPES / "elster_transmission" / "transmission.py"
SOURCES = (CONTROLLER, SCRIPT, APP / "dauerfrist_sources.py")
TABLES = ("vat_return_extension", "vat_return_extension_base")
PRINT_FORMAT = APP / "steuerbote" / "print_format" / "dauerfristverlängerung"
# German terms and values that read the same in every language, the status of a form among them.
UNTRANSLATED = frozenset(
	{
		"Abgegeben",
		"Berechnet",
		"Bereit",
		"Entwurf",
		"Kz 39",
		"Kz 83",
		"Sondervorauszahlung",
		"Sondervorauszahlung (Kz 38)",
		"Transferticket",
	}
)
# Labels Frappe and ERPNext translate themselves; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{"Amended From", "Date of Establishment", "Due Date", "Remarks", "Series", "Status"}
)
TRANSLATED_LITERAL = re.compile(r"\b_{1,2}\(\s*\"((?:[^\"\\]|\\.)*)\"")
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
CLASS_ATTRIBUTE = re.compile(r'\bclass="([^"]*)"')
CLASS_SELECTOR = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
SVZ = Context.UMSATZSTEUERSONDERVORAUSZAHLUNG


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def doctype(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def fields(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in doctype(name)["fields"]}


def texts_of_the_dauerfrist() -> set[str]:
	texts = set(FORM_MESSAGES)
	for name in TABLES:
		definition = doctype(name)
		texts.update({definition["name"], definition["description"]})
		for field in definition["fields"]:
			texts.update(field[key] for key in ("label", "description") if field.get(key))
			if field["fieldtype"] == "Select" and field["fieldname"] != "naming_series":
				texts.update(
					option for option in field["options"].split("\n") if option and not option.isdigit()
				)
	for source in SOURCES:
		texts.update(TRANSLATED_LITERAL.findall(source.read_text(encoding="utf-8")))
	return texts - UNTRANSLATED - FRAMEWORK_LABELS


def whitelisted_methods() -> set[str]:
	"""The whitelisted methods of the controller and of Transmittable, from which it inherits."""
	classes = (
		node
		for source in (CONTROLLER, TRANSMITTABLE)
		for node in ast.parse(source.read_text(encoding="utf-8")).body
		if isinstance(node, ast.ClassDef)
	)
	return {
		method.name
		for cls in classes
		for method in cls.body
		if isinstance(method, ast.FunctionDef)
		and any("whitelist" in ast.unparse(decorator) for decorator in method.decorator_list)
	}


class TranslationsTest(TestCase):
	def test_the_sources_are_read(self):
		texts = texts_of_the_dauerfrist()
		for text in (
			"VAT Return Extension",
			"Entered in Mein ELSTER",
			"Calculate the form before filing it.",
			"Steuerbote does not know form USt 1 H for {0} yet.",
			"Umsatzsteuersondervorauszahlung",
		):
			with self.subTest(text=text):
				self.assertIn(text, texts)

	def test_every_text_of_the_dauerfrist_is_translated(self):
		self.assertEqual(sorted(texts_of_the_dauerfrist() - set(translations())), [])

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & set(translations())), [])

	def test_the_document_carries_its_german_names(self):
		german = translations()
		self.assertEqual(german["VAT Return Extension"], "Dauerfristverlängerung")
		self.assertEqual(
			[
				german[option]
				for option in fields("vat_return_extension")["context"]["options"].split("\n")[1:]
			],
			["Antrag auf Dauerfristverlängerung", "Anmeldung der Sondervorauszahlung"],
		)


class DocumentTest(TestCase):
	def setUp(self):
		self.definition = doctype("vat_return_extension")
		self.fields = fields("vat_return_extension")

	def test_is_a_submittable_document_numbered_per_year(self):
		self.assertEqual(
			{key: self.definition[key] for key in ("name", "module", "is_submittable", "autoname")},
			{
				"name": "VAT Return Extension",
				"module": "Steuerbote",
				"is_submittable": 1,
				"autoname": "naming_series:",
			},
		)
		self.assertEqual(self.fields["naming_series"]["options"], "DFV-.{year}.-.#####")

	def test_the_contexts_are_those_of_the_core(self):
		options = self.fields["context"]["options"].split("\n")
		self.assertEqual(options, ["", *(context.value for context in Context)])

	def test_the_fields_of_the_sondervorauszahlung_appear_with_it(self):
		condition = f"eval:doc.context === '{SVZ.value}'"
		for fieldname in ("is_correction", "crediting_period_label", "base_section", "offset_requested"):
			with self.subTest(field=fieldname):
				self.assertEqual(self.fields[fieldname]["depends_on"], condition)

	def test_what_calculate_finds_is_read_only_and_not_copied(self):
		for fieldname in (
			"base_rows",
			"missing_periods",
			"kz83",
			"kz39",
			"established_on",
			"months_active",
			"computed_base",
			"base",
			"sondervorauszahlung",
			"findings",
			"filed_via",
			"filed_on",
			"transferticket",
			"filing_note",
		):
			with self.subTest(field=fieldname):
				self.assertEqual(
					(self.fields[fieldname]["read_only"], self.fields[fieldname]["no_copy"]), (1, 1)
				)

	def test_the_lock_of_a_transmission_is_read_only_and_not_copied(self):
		lock = self.fields["transmission_in_progress"]
		self.assertEqual(
			(lock["fieldtype"], lock["read_only"], lock["no_copy"], lock["label"]),
			("Check", 1, 1, "Transmission Running"),
		)
		self.assertEqual(
			self.definition["field_order"].index("transmission_in_progress"),
			self.definition["field_order"].index("status") + 1,
		)

	def test_a_form_is_filed_through_eric_mein_elster_or_another_way(self):
		self.assertEqual(
			self.fields["filed_via"]["options"].split("\n"), ["", "mein_elster", "other_way", "eric"]
		)
		source = CONTROLLER.read_text(encoding="utf-8")
		self.assertIn('FILED_THROUGH_ERIC = "eric"', source)

	def test_names_the_provisional_forms_of_its_year_after_the_lock_of_a_transmission(self):
		field = self.fields["provisional"]
		self.assertEqual(
			{key: field.get(key) for key in ("fieldtype", "label", "read_only", "default")},
			{"fieldtype": "Check", "label": "Provisional Forms", "read_only": 1, "default": "0"},
		)
		order = self.definition["field_order"]
		self.assertEqual(order.index("provisional"), order.index("transmission_in_progress") + 1)
		self.assertIn("vorläufig", translations()[field["description"]])

	def test_the_base_lists_the_filed_vat_returns(self):
		base = fields("vat_return_extension_base")
		self.assertEqual(self.fields["base_rows"]["options"], "VAT Return Extension Base")
		self.assertEqual(base["vat_return"]["options"], "VAT Return")
		self.assertTrue(doctype("vat_return_extension_base")["istable"])


class FormScriptTest(TestCase):
	"""A draft is filed through ELSTER or a note of its filing, never by Buchen alone."""

	def setUp(self):
		self.script = SCRIPT.read_text(encoding="utf-8")
		self.shared = SHARED_SCRIPT.read_text(encoding="utf-8")

	def test_a_draft_gets_no_hint_to_submit_it(self):
		setup = re.search(r"\n\tsetup\(frm\) \{\n(?P<body>.*?)\n\t\},\n", self.script, re.DOTALL)
		self.assertIsNotNone(setup)
		self.assertIn("frm.show_submit_message = () => {};", setup["body"])
		self.assertIn("offer_buchen_only_for_an_accepted_send(frm);", self.script)
		self.assertIn("frm.page.clear_primary_action();", self.shared)

	def test_the_buttons_call_whitelisted_methods(self):
		called = set(re.findall(r'frm\s*\.call\("(\w+)"', self.script + self.shared))
		self.assertEqual(
			called, {"calculate", "mark_filed_outside", "transmit", "release_stale_transmission"}
		)
		self.assertEqual(called - whitelisted_methods(), set())

	def test_the_form_offers_the_transmission_beside_the_notes_of_a_filing(self):
		(buttons,) = re.findall(r"function add_filing_buttons\(frm\) \{\n(.*?)\n\}\n", self.script, re.DOTALL)
		self.assertIn("add_transmission_buttons(frm, group, form_texts());", buttons)
		self.assertEqual(
			re.findall(r'frm\.add_custom_button\(__\("([^"]+)"\)', buttons),
			["Entered in Mein ELSTER", "Mark as Filed Outside"],
		)

	def test_the_intro_says_the_form_is_entered_in_mein_elster_by_hand(self):
		(intro,) = (
			text for text in TRANSLATED_LITERAL.findall(self.script) if text.startswith("Mein ELSTER")
		)
		self.assertIn("Mein ELSTER bietet für den Vordruck USt 1 H kein Hochladen an", translations()[intro])


class PrintFormatFilesTest(TestCase):
	def setUp(self):
		self.record = json.loads((PRINT_FORMAT / "dauerfristverlängerung.json").read_text(encoding="utf-8"))
		self.template = (PRINT_FORMAT / "dauerfristverlängerung.html").read_text(encoding="utf-8")

	def test_is_a_standard_jinja_format_of_the_dauerfrist(self):
		self.assertEqual(
			{
				key: self.record[key]
				for key in ("name", "doc_type", "print_format_type", "standard", "module", "custom_format")
			},
			{
				"name": "Dauerfristverlängerung",
				"doc_type": "VAT Return Extension",
				"print_format_type": "Jinja",
				"standard": "Yes",
				"module": "Steuerbote",
				"custom_format": 0,
			},
		)

	def test_lies_where_frappe_looks_for_its_template(self):
		"""Frappe reads the template of a standard print format from the folder of its scrubbed name."""
		scrubbed = self.record["name"].replace(" ", "_").replace("-", "_").lower()
		self.assertEqual(PRINT_FORMAT.name, scrubbed)

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

	def test_keeps_to_classes_of_its_own(self):
		used = {name for value in CLASS_ATTRIBUTE.findall(self.template) for name in value.split()}
		styled = set(CLASS_SELECTOR.findall(self.record["css"]))
		self.assertEqual(sorted(name for name in used | styled if not name.startswith("sb-")), [])
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
				"Verlängert ab",
				"Fällig am",
				"Angerechnet in Kz 39 von",
				"Vordruck",
				"Abgegeben über",
				"Abgegeben am",
				"Transferticket",
				"Wie und wann abgegeben",
			],
		)

	def test_marks_the_form_of_a_provisional_year_under_the_title(self):
		self.assertIn("{%- set provisional = doc.provisional_forms() %}", self.template)
		self.assertIn(
			'<p class="sb-subtitle">vorläufig ({{ provisional.documentation }}, Vordruck {{ provisional.form_year }})</p>',
			self.template,
		)
		self.assertLess(self.template.index("<h1>"), self.template.index("vorläufig ("))

	def test_the_lines_carry_the_labels_of_the_form(self):
		layout = layout_for(2026)
		for element, line in (("Kz10", 7), ("Kz29", 10), ("Kz26", 11)):
			field = layout.field(SVZ, element)
			with self.subTest(element=element):
				self.assertEqual(field.line, line)
				self.assertIn(
					f'flag_row({line}, "{element.removeprefix("Kz")}", "{field.label}",', self.template
				)
		kz38 = layout.field(SVZ, "Kz38")
		self.assertEqual((kz38.line, kz38.label), (9, "Davon 1/11 = Sondervorauszahlung 2026"))
		self.assertIn("<td>Davon 1/11 = Sondervorauszahlung {{ doc.year }}</td>", self.template)
		self.assertIn(layout.field(SVZ, "Kz500").label, self.template)
		self.assertIn(layout.field(SVZ, "Kz500_Begruendung").label, self.template)
