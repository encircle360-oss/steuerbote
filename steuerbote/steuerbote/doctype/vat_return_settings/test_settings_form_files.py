"""The forms of the Voranmeldung, its settings and the Dauerfristverlängerung show the values of their select fields in
the timeline as the form does, in German, and the settings warn when a change of the rules of the period touches
filed periods; read from their files without a bench."""

import re
from pathlib import Path
from unittest import TestCase

APP = Path(__file__).resolve().parents[3]
DOCTYPES = APP / "steuerbote" / "doctype"
SCRIPT = APP / "public" / "js" / "timeline_values.js"
INCLUDE = '{% include "steuerbote/public/js/timeline_values.js" %}'
FORMS = {
	"VAT Return": DOCTYPES / "vat_return" / "vat_return.js",
	"VAT Return Settings": DOCTYPES / "vat_return_settings" / "vat_return_settings.js",
	"VAT Return Extension": DOCTYPES / "vat_return_extension" / "vat_return_extension.js",
}
SETTINGS = DOCTYPES / "vat_return_settings" / "vat_return_settings.py"


class TimelineValuesTest(TestCase):
	def test_each_form_includes_the_script_and_translates_its_timeline(self):
		for doctype, path in FORMS.items():
			with self.subTest(doctype=doctype):
				form = path.read_text(encoding="utf-8")
				self.assertIn(INCLUDE, form)
				self.assertRegex(
					form, r"timeline_refresh\(frm\) \{\n\t\ttranslate_select_values_in_timeline\(frm\);"
				)

	def test_the_script_translates_the_old_and_the_new_value_of_a_select_field_once(self):
		script = SCRIPT.read_text(encoding="utf-8")
		(function,) = re.findall(
			r"function translate_select_values_in_timeline\(frm\) \{.*?\n\}", script, re.DOTALL
		)
		self.assertIn('df.fieldtype === "Select"', function)
		self.assertIn("__(", function)
		self.assertIn("frm.timeline.render_timeline_items();", function)
		self.assertIn("steuerbote_translated", function)


class RuleChangeWarningTest(TestCase):
	def test_the_settings_name_their_filed_periods_and_the_form_warns_on_a_change_of_the_rules(self):
		self.assertIn('self.set_onload("filed_periods", filed_periods(self.company))', SETTINGS.read_text())
		form = FORMS["VAT Return Settings"].read_text(encoding="utf-8")
		for field in ("period_basis", "late_documents"):
			with self.subTest(field=field):
				self.assertIn(f"{field}(frm) {{\n\t\twarn_of_filed_periods(frm);", form)


class ListIndicatorTest(TestCase):
	"""The lists of the Voranmeldung and the Dauerfristverlängerung show the status Steuerbote sets, not only whether
	the document is a draft."""

	def test_each_list_shows_every_status_of_its_doctype(self):
		import json

		for name, doctype in (("vat_return", "VAT Return"), ("vat_return_extension", "VAT Return Extension")):
			with self.subTest(doctype=doctype):
				script = (DOCTYPES / name / f"{name}_list.js").read_text(encoding="utf-8")
				self.assertIn(f'frappe.listview_settings["{doctype}"]', script)
				self.assertIn('add_fields: ["status"]', script)
				definition = json.loads((DOCTYPES / name / f"{name}.json").read_text(encoding="utf-8"))
				(status,) = (field for field in definition["fields"] if field["fieldname"] == "status")
				for option in status["options"].split("\n"):
					self.assertIn(f"{option}:", script)


class VatReturnFormTest(TestCase):
	def setUp(self):
		self.form = FORMS["VAT Return"].read_text(encoding="utf-8")
		self.controller = (DOCTYPES / "vat_return" / "vat_return.py").read_text(encoding="utf-8")

	def test_a_filed_return_offers_no_cancellation_the_server_refuses(self):
		self.assertIn('self.set_onload("cancellable", self.cancellable())', self.controller)
		self.assertIn("frm.page.clear_secondary_action();", self.form)

	def test_the_note_of_a_filing_keeps_its_dialog_open_until_the_server_takes_it(self):
		(ask,) = re.findall(r"function ask_for_filing_note\(frm, filed_via\) \{.*?\n\}", self.form, re.DOTALL)
		self.assertIn("new frappe.ui.Dialog(", ask)
		self.assertNotIn("frappe.prompt(", ask)
		self.assertIn("dialog.hide();", ask)
		self.assertIn("TRANSFERTICKET.test(", ask)
		(pattern,) = re.findall(r"const TRANSFERTICKET = /\^(.*)\$/;", self.form)
		self.assertIn(pattern, self.controller)


class ExtensionFormTest(TestCase):
	def test_the_missing_periods_hide_while_a_base_by_hand_with_its_reason_applies(self):
		import json

		definition = json.loads(
			(DOCTYPES / "vat_return_extension" / "vat_return_extension.json").read_text(encoding="utf-8")
		)
		(field,) = (field for field in definition["fields"] if field["fieldname"] == "missing_periods")
		self.assertEqual(field.get("depends_on"), "eval:doc.missing_periods && !(doc.base_override_reason || '').trim()")
