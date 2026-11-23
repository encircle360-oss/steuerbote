"""The records the deadlines come with fit together, read from their files without a bench: the report Offene
Fristen, the Deadline Reminder, the fields of the VAT Return Settings, the daily job in hooks.py and the DocTypes of the
annual filings, which come with their modules."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote import hooks
from steuerbote.deadlines import DOCUMENT_TYPES, Kind, annual

APP = Path(__file__).resolve().parents[2]
MODULE = APP / "steuerbote"
REPORT = MODULE / "report" / "offene_fristen"
REMINDER = MODULE / "doctype" / "deadline_reminder" / "deadline_reminder.json"
SETTINGS = MODULE / "doctype" / "vat_return_settings" / "vat_return_settings.json"
TRANSLATIONS = APP / "translations" / "de.csv"
JOB = "steuerbote.steuerbote.deadlines.send_reminders"
REMINDER_FIELDS = ["deadlines_section", "deadline_recipients", "column_break_deadlines", "reminder_days"]


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def module_body(path: Path) -> list[ast.stmt]:
	return ast.parse(path.read_text(encoding="utf-8")).body


def constants(path: Path) -> dict[str, object]:
	"""The literal values the module assigns to names at its top level."""
	return {
		target.id: ast.literal_eval(node.value)
		for node in module_body(path)
		if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
		for target in node.targets
		if isinstance(target, ast.Name)
	}


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


class ReportFilesTest(TestCase):
	def test_the_report_is_a_standard_script_report_of_the_module(self):
		report = read_json(REPORT / "offene_fristen.json")
		self.assertEqual(
			{
				key: report[key]
				for key in ("name", "report_name", "report_type", "ref_doctype", "is_standard", "module")
			},
			{
				"name": "Offene Fristen",
				"report_name": "Offene Fristen",
				"report_type": "Script Report",
				"ref_doctype": "VAT Return",
				"is_standard": "Yes",
				"module": "Steuerbote",
			},
		)
		self.assertEqual(
			sorted(role["role"] for role in report["roles"]),
			["Accounts Manager", "Accounts User", "System Manager"],
		)

	def test_the_filters_of_the_script_are_those_the_report_reads(self):
		script = (REPORT / "offene_fristen.js").read_text(encoding="utf-8")
		values = constants(REPORT / "offene_fristen.py")
		self.assertEqual(re.findall(r'fieldname: "(\w+)"', script), [values["COMPANY"], values["HORIZON"]])
		self.assertEqual(re.findall(r"default: (\d+)", script), [str(values["DEFAULT_HORIZON"])])

	def test_the_report_and_the_job_name_the_same_report(self):
		self.assertEqual(
			constants(MODULE / "deadlines.py")["REPORT"], read_json(REPORT / "offene_fristen.json")["name"]
		)


class ReminderFilesTest(TestCase):
	def setUp(self):
		self.doctype = read_json(REMINDER)
		self.fields = {field["fieldname"]: field for field in self.doctype["fields"]}

	def test_records_the_company_the_deadline_and_the_day(self):
		self.assertEqual(
			[
				(name, field["fieldtype"])
				for name, field in self.fields.items()
				if field["fieldtype"] != "Column Break"
			],
			[
				("company", "Link"),
				("kind", "Select"),
				("period_label", "Data"),
				("due_date", "Date"),
				("sent_on", "Date"),
			],
		)
		self.assertEqual(self.doctype["field_order"], list(self.fields))

	def test_names_each_kind_of_deadline_as_the_deadlines_do(self):
		self.assertEqual(self.fields["kind"]["options"].split("\n"), [kind.value for kind in Kind])

	def test_only_the_server_writes_a_reminder(self):
		self.assertEqual(self.doctype["in_create"], 1)
		for field in self.fields.values():
			if field["fieldtype"] != "Column Break":
				with self.subTest(field=field["fieldname"]):
					self.assertEqual((field.get("read_only"), field.get("reqd")), (1, 1))
		for permission in self.doctype["permissions"]:
			with self.subTest(role=permission["role"]):
				self.assertFalse(
					permission.get("write") or permission.get("create") or permission.get("submit")
				)

	def test_is_named_by_its_controller(self):
		self.assertEqual(self.doctype["naming_rule"], "By script")
		self.assertNotIn("autoname", self.doctype)
		controller = module_body(REMINDER.with_suffix(".py"))
		(document,) = [node for node in controller if isinstance(node, ast.ClassDef)]
		self.assertIn("autoname", {node.name for node in document.body if isinstance(node, ast.FunctionDef)})

	def test_each_kind_is_filed_with_a_doctype_of_the_module_or_awaits_it(self):
		names = {read_json(path)["name"] for path in (MODULE / "doctype").glob("*/*.json")}
		self.assertLessEqual(set(DOCUMENT_TYPES.values()) - names, set(annual.AWAITING_DOCTYPES))
		self.assertLessEqual(
			{doctype for kind, doctype in DOCUMENT_TYPES.items() if kind not in annual.KINDS}, names
		)


class SettingsFilesTest(TestCase):
	def setUp(self):
		self.settings = read_json(SETTINGS)
		self.fields = {field["fieldname"]: field for field in self.settings["fields"]}

	def test_the_settings_hold_the_reminder_in_a_section_of_its_own(self):
		order = self.settings["field_order"]
		start = order.index(REMINDER_FIELDS[0])
		self.assertEqual(order[start : start + len(REMINDER_FIELDS)], REMINDER_FIELDS)
		section = self.fields["deadlines_section"]
		self.assertEqual(
			(section["fieldtype"], translations()[section["label"]]), ("Section Break", "Fristen")
		)

	def test_the_recipients_are_text_and_the_days_of_notice_a_number_from_seven_on(self):
		recipients, days = self.fields["deadline_recipients"], self.fields["reminder_days"]
		self.assertEqual(recipients["fieldtype"], "Small Text")
		self.assertEqual((days["fieldtype"], days["default"], days["non_negative"]), ("Int", "7", 1))


class SchedulerTest(TestCase):
	def test_the_daily_job_sends_the_reminders(self):
		self.assertIn(JOB, hooks.scheduler_events["daily"])
		module, _, function = JOB.rpartition(".")
		path = APP.parent.joinpath(*module.split(".")).with_suffix(".py")
		jobs = {node.name: node for node in module_body(path) if isinstance(node, ast.FunctionDef)}
		self.assertEqual(jobs[function].args.args, [])
