"""The table Abgleich mit Registern of the VAT Return, read from its files without a bench: its texts read in German,
the form lets the user write the explanations alone and leaves the values of a row not compared blank, and the file
for Mein ELSTER waits for every difference to be explained, as the controller does."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.ustva.registers import Register

APP = Path(__file__).resolve().parents[3]
DOCTYPES = APP / "steuerbote" / "doctype"
TRANSLATIONS = APP / "translations" / "de.csv"
FOLDER = DOCTYPES / "vat_return"
TABLE = "vat_return_register_reconciliation"
VAT_RETURN_FIELDS = ("register_section", "register_reconciliation")
# Labels Frappe and ERPNext translate themselves, among them the names of the two reports; the app keeps out of
# their translations, so that the reports read the same here as in the menu of ERPNext.
FRAMEWORK_LABELS = frozenset({"Difference", "Report", *(register.value for register in Register)})
# Labels the app translated before, for other tables.
TRANSLATED_BEFORE = frozenset({"Account", "Kennzahl", "Ledger Amount"})
TRANSLATED_LITERAL = re.compile(r'\b_{1,2}\(\s*"((?:[^"\\]|\\.)*)"')


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def doctype(name: str) -> dict:
	return json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))


def fields(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in doctype(name)["fields"]}


def field_texts(definitions) -> set[str]:
	texts = set()
	for field in definitions:
		texts.update(field[key] for key in ("label", "description") if field.get(key))
		if field["fieldtype"] == "Select":
			texts.update(option for option in field["options"].split("\n") if option)
	return texts


def function(script: str, name: str) -> str:
	found = re.search(rf"\nfunction {name}\([^)]*\) \{{\n(?P<body>.*?)\n\}}\n", script, re.DOTALL)
	if found is None:
		raise ValueError(f"vat_return.js has no function {name}")
	return found["body"]


class TranslationsTest(TestCase):
	def test_every_text_of_the_table_its_section_and_its_message_is_translated(self):
		definition = doctype(TABLE)
		texts = {definition["name"], definition["description"], *field_texts(definition["fields"])}
		texts.update(field_texts(fields("vat_return")[name] for name in VAT_RETURN_FIELDS))
		controller = (FOLDER / "vat_return.py").read_text(encoding="utf-8")
		texts.update(text for text in TRANSLATED_LITERAL.findall(controller) if "registers" in text)
		self.assertIn("Explanation", texts)
		self.assertTrue(any(text.startswith("The reconciliation with the registers") for text in texts))
		self.assertEqual(sorted(texts - set(translations()) - FRAMEWORK_LABELS - TRANSLATED_BEFORE), [])

	def test_the_reports_and_framework_labels_are_left_to_frappe_and_erpnext(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & set(translations())), [])

	def test_the_table_reads_in_german(self):
		german = translations()
		self.assertEqual(german["Reconciliation with Registers"], "Abgleich mit Registern")
		self.assertEqual(german["Explanation"], "Erklärung")


class FormTest(TestCase):
	def setUp(self):
		self.script = (FOLDER / "vat_return.js").read_text(encoding="utf-8")

	def test_the_section_appears_with_its_rows(self):
		vat_return = fields("vat_return")
		self.assertEqual(
			vat_return["register_section"]["depends_on"], "eval:(doc.register_reconciliation || []).length"
		)
		self.assertEqual(
			vat_return["register_reconciliation"]["options"], "VAT Return Register Reconciliation"
		)

	def test_the_user_writes_the_explanations_and_nothing_else(self):
		table = fields("vat_return")["register_reconciliation"]
		self.assertEqual((table["cannot_add_rows"], table["cannot_delete_rows"]), (1, 1))
		self.assertNotIn("read_only", table)
		columns = fields(TABLE)
		self.assertEqual(
			sorted(name for name, field in columns.items() if not field.get("read_only")), ["explanation"]
		)
		self.assertEqual(columns["explanation"]["fieldtype"], "Small Text")

	def test_the_form_leaves_the_values_of_a_row_not_compared_blank(self):
		setup = re.search(r"\n\tsetup\(frm\) \{\n(?P<body>.*?)\n\t\},\n", self.script, re.DOTALL)
		self.assertIsNotNone(setup)
		self.assertIn("leave_what_is_not_compared_blank();", setup["body"])
		body = function(self.script, "leave_what_is_not_compared_blank")
		self.assertIn('for (const fieldname of ["ledger_amount", "difference"])', body)
		self.assertIn(
			'frappe.meta.set_formatter("VAT Return Register Reconciliation", fieldname, null,', body
		)
		self.assertIn('"<span></span>"', body)
		columns = fields(TABLE)
		self.assertEqual((columns["compared"]["fieldtype"], columns["compared"]["hidden"]), ("Check", 1))

	def test_the_file_for_mein_elster_waits_for_the_explanations_or_the_remarks(self):
		offer = function(self.script, "can_make_import_file")
		self.assertIn("(remarks || !unexplained_differences(doc).length)", offer)
		rows = function(self.script, "unexplained_differences")
		self.assertIn('flt(row.difference) && !(row.explanation || "").trim()', rows)
