"""The confirmations of the USt-IdNrn. of partners, read from their files without a bench: the hooks that start them,
the custom fields on Customer, Supplier and Sales Invoice, the settings with their defaults, the fields of the VAT ID
Confirmation, the worklist report, the forms, and that every text reads in German."""

import ast
import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote import hooks
from steuerbote.vatid.partners import Level, Standing

APP = Path(__file__).resolve().parents[1]
MODULE = APP / "steuerbote"
DOCTYPES = MODULE / "doctype"
PARTNERS = MODULE / "partner_vat_ids.py"
SETUP = MODULE / "vat_id_setup.py"
CONFIRMING = DOCTYPES / "vat_id_confirmation" / "confirming.py"
REPORT_NAME = "Partner ohne aktuelle USt-IdNr-Bestätigung"
REPORT = MODULE / "report" / REPORT_NAME.replace(" ", "_").replace("-", "_").lower()
SCRIPTS = APP / "public" / "js"
PARTNER_SCRIPT = SCRIPTS / "partner_vat_id.js"
INVOICE_SCRIPT = SCRIPTS / "sales_invoice_vat_id.js"
SHARED_SCRIPT = SCRIPTS / "vat_id_confirmation.js"
TRANSLATIONS = APP / "translations" / "de.csv"
PY_TRANSLATED = re.compile(r"\b_\(\s*\"((?:[^\"\\]|\\.)*)\"")
JS_TRANSLATED = re.compile(r"\b__\(\s*\"((?:[^\"\\]|\\.)*)\"")
# Labels Frappe and ERPNext translate themselves.
FRAMEWORK = frozenset(
	{
		"Company",
		"Current",
		"Customer",
		"Expired",
		"Invalid",
		"Invoice",
		"Manual",
		"Missing",
		"No Answer",
		"Note",
		"Off",
		"Party",
		"Party Type",
		"Result",
		"Sales Invoice",
		"Supplier",
		"Tax",
		"Valid",
		"Warn",
	}
)
PARTY_FIELDS = ("steuernummer", "foreign_tax_id", "vat_id_status", "vat_id_checked_on", "vat_id_confirmation")
INVOICE_FIELDS = ("vat_id_confirmation", "vat_id_override_reason")


def read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def read_json(path: Path):
	return json.loads(read(path))


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def assignments(path: Path) -> dict[str, ast.expr]:
	return {
		node.targets[0].id: node.value
		for node in ast.parse(read(path)).body
		if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
	}


def literal(path: Path, name: str):
	"""The value of a module-level constant, which may name the constants before it."""
	namespace: dict[str, object] = {}
	for node in ast.parse(read(path)).body:
		if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
			try:
				namespace[node.targets[0].id] = eval(  # noqa: S307 - constants of the app's own files
					compile(ast.Expression(node.value), str(path), "eval"),
					{"__builtins__": {}},
					dict(namespace),
				)
			except Exception:  # noqa: S112 - a value that is no constant is not wanted
				continue
	return namespace[name]


def fields_of(doctype: str) -> dict[str, dict]:
	return {
		field["fieldname"]: field for field in read_json(DOCTYPES / doctype / f"{doctype}.json")["fields"]
	}


def custom_fields() -> dict[tuple[str, str], dict]:
	return {
		(field["dt"], field["fieldname"]): field
		for field in read_json(APP / "fixtures" / "custom_field.json")
	}


def python_texts(path: Path) -> set[str]:
	source = read(path)
	texts = set(PY_TRANSLATED.findall(source))
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_" and node.args:
			argument = node.args[0]
			if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
				texts.add(argument.value)
	return texts


class HookFilesTest(TestCase):
	def test_a_change_of_a_partner_or_its_address_and_the_submit_of_an_invoice_reach_the_module(self):
		partners = "steuerbote.steuerbote.partner_vat_ids"
		self.assertEqual(
			{
				doctype: hooks.doc_events[doctype]
				for doctype in ("Customer", "Supplier", "Address", "Sales Invoice")
			},
			{
				"Customer": {"on_update": f"{partners}.on_party_update"},
				"Supplier": {"on_update": f"{partners}.on_party_update"},
				"Address": {"on_update": f"{partners}.on_address_update"},
				"Sales Invoice": {"before_submit": f"{partners}.check_invoice"},
			},
		)
		self.assertIn("File", hooks.doc_events)

	def test_the_renewal_runs_each_morning_after_the_maintenance_of_the_bzst(self):
		(schedule,) = hooks.scheduler_events["cron"]
		self.assertEqual(
			hooks.scheduler_events["cron"][schedule],
			["steuerbote.steuerbote.partner_vat_ids.renew_confirmations"],
		)
		minute, hour, *rest = schedule.split()
		self.assertEqual(rest, ["*", "*", "*"])
		self.assertTrue(5 <= int(hour) < 23 and 0 <= int(minute) < 60)
		self.assertIn("steuerbote.steuerbote.partner_vat_ids.fill_statuses", hooks.after_migrate)

	def test_the_forms_load_their_scripts_and_list_the_confirmations(self):
		self.assertEqual(
			hooks.doctype_js,
			{
				"Customer": "public/js/partner_vat_id.js",
				"Supplier": "public/js/partner_vat_id.js",
				"Sales Invoice": "public/js/sales_invoice_vat_id.js",
			},
		)
		for path in hooks.doctype_js.values():
			self.assertTrue((APP / path).is_file(), path)
		self.assertEqual(
			hooks.override_doctype_dashboards,
			{
				"Customer": "steuerbote.steuerbote.partner_vat_ids.customer_dashboard",
				"Supplier": "steuerbote.steuerbote.partner_vat_ids.supplier_dashboard",
			},
		)

	def test_the_setup_offers_the_label_and_the_job_of_erpnext_germany_as_steps(self):
		steps = {step["key"]: step for step in hooks.steuerbote_setup_steps}
		self.assertEqual(
			steps["vat_id_label"]["run"], "steuerbote.steuerbote.vat_id_setup.check_tax_id_label"
		)
		self.assertEqual(
			steps["erpnext_germany_vat_id_check"]["run"],
			"steuerbote.steuerbote.vat_id_setup.check_erpnext_germany",
		)
		source = read(SETUP)
		for method in ("relabel_tax_id", "stop_erpnext_germany_check"):
			with self.subTest(method=method):
				self.assertRegex(source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\ndef {method}\(')
				self.assertIn(f'f"{{__name__}}.{method}"', source)
		self.assertNotIn("import erpnext_germany", source)
		self.assertEqual(
			steps["vat_id_automatic_check"]["run"], "steuerbote.steuerbote.vat_id_setup.check_automatic_check"
		)
		self.assertRegex(source, r'@frappe\.whitelist\(methods=\["POST"\]\)\ndef enable_automatic_check\(')


class FieldFilesTest(TestCase):
	def test_customer_and_supplier_get_the_identifiers_and_the_status(self):
		fields = custom_fields()
		statuses = literal(PARTNERS, "STATUSES")
		for doctype in ("Customer", "Supplier"):
			with self.subTest(doctype=doctype):
				ours = [fields[(doctype, name)] for name in PARTY_FIELDS]
				self.assertEqual([field["insert_after"] for field in ours], ["tax_id", *PARTY_FIELDS[:-1]])
				self.assertEqual({field["module"] for field in ours}, {"Steuerbote"})
				self.assertEqual(
					[field["fieldtype"] for field in ours], ["Data", "Data", "Select", "Date", "Link"]
				)
				self.assertEqual(ours[2]["options"].split("\n"), list(statuses))
				self.assertEqual([field["read_only"] for field in ours], [0, 0, 1, 1, 1])
				self.assertEqual(fields[(doctype, "vat_id_confirmation")]["options"], "VAT ID Confirmation")

	def test_the_invoice_keeps_its_confirmation_and_the_reason_to_submit_all_the_same(self):
		fields = custom_fields()
		link, reason = (fields[("Sales Invoice", name)] for name in INVOICE_FIELDS)
		self.assertEqual(
			(link["fieldtype"], link["options"], link["read_only"], link["no_copy"]),
			("Link", "VAT ID Confirmation", 1, 1),
		)
		self.assertEqual(
			(reason["fieldtype"], reason["no_copy"], reason["allow_on_submit"]), ("Small Text", 1, 0)
		)
		self.assertEqual(literal(PARTNERS, "OVERRIDE_FIELD"), "vat_id_override_reason")

	def test_the_settings_send_nothing_by_themselves_and_block_goods_by_default(self):
		fields = fields_of("vat_return_settings")
		self.assertEqual(
			{
				name: field.get("default")
				for name, field in fields.items()
				if name.startswith("vat_id_") and field["fieldtype"] not in ("Section Break", "Column Break")
			},
			{
				"vat_id_check_on_change": "0",
				"vat_id_renewal": "0",
				"vat_id_check_suppliers": "1",
				"vat_id_invoice_goods": "Block",
				"vat_id_goods_max_age": "0",
				"vat_id_invoice_services": "Warn",
			},
		)
		for name in ("vat_id_invoice_goods", "vat_id_invoice_services"):
			self.assertEqual(fields[name]["options"].split("\n"), [level.value for level in Level])
		self.assertEqual(fields["max_confirmation_age"]["default"], "90")

	def test_a_confirmation_names_its_partner_its_invoice_and_what_started_it(self):
		fields = fields_of("vat_id_confirmation")
		self.assertEqual(
			(fields["party_type"]["options"], fields["party"]["fieldtype"], fields["party"]["options"]),
			("DocType", "Dynamic Link", "party_type"),
		)
		self.assertEqual(fields["sales_invoice"]["options"], "Sales Invoice")
		self.assertEqual(fields["started_by"]["options"].split("\n"), ["", *literal(PARTNERS, "TRIGGERS")])
		self.assertTrue(
			all(fields[name]["read_only"] for name in ("party_type", "party", "sales_invoice", "started_by"))
		)
		self.assertIn(
			'"Sales Invoice": "sales_invoice"',
			read(DOCTYPES / "vat_id_confirmation" / "vat_id_confirmation.py"),
		)


class ReportFilesTest(TestCase):
	def test_the_worklist_is_a_standard_script_report_of_the_confirmations(self):
		report = read_json(REPORT / f"{REPORT.name}.json")
		self.assertEqual(
			{
				key: report[key]
				for key in ("name", "report_name", "report_type", "ref_doctype", "is_standard", "module")
			},
			{
				"name": REPORT_NAME,
				"report_name": REPORT_NAME,
				"report_type": "Script Report",
				"ref_doctype": "VAT ID Confirmation",
				"is_standard": "Yes",
				"module": "Steuerbote",
			},
		)
		self.assertEqual(
			sorted(role["role"] for role in report["roles"]),
			["Accounts Manager", "Accounts User", "System Manager"],
		)

	def test_the_filters_of_the_script_are_those_the_report_reads(self):
		script = read(REPORT / f"{REPORT.name}.js")
		self.assertIn(f'frappe.query_reports["{REPORT_NAME}"]', script)
		self.assertEqual(
			tuple(re.findall(r'fieldname: "(\w+)"', script)), literal(REPORT / f"{REPORT.name}.py", "FILTERS")
		)

	def test_every_standing_on_the_list_has_its_note(self):
		notes = literal(REPORT / f"{REPORT.name}.py", "STANDING_NOTES")
		with_reason = {Standing.NOT_CONFIRMABLE.value, Standing.MALFORMED.value}
		self.assertEqual(set(notes) | with_reason, {standing.value for standing in Standing if standing.work})


class FormFilesTest(TestCase):
	def test_the_partner_asks_before_anything_leaves_and_names_what_leaves(self):
		script = read(PARTNER_SCRIPT)
		self.assertIn('"steuerbote.steuerbote.partner_vat_ids.confirm_vat_id"', script)
		self.assertIn("frappe.confirm(question", script)
		for item in (
			"own USt-IdNr.",
			"name, street, postal code and town",
			"VIES of the European Commission",
		):
			self.assertIn(item, script)
		self.assertIn("if (state.can_ask)", script)

	def test_the_dialog_of_a_return_and_a_statement_names_what_leaves_and_shows_only_with_numbers_to_confirm(
		self,
	):
		shared = read(SHARED_SCRIPT)
		self.assertIn(
			"frappe.confirm(`${question}<br><br>${what_leaves_the_site(frm)}<br><br>${live}`", shared
		)
		for script in (
			DOCTYPES / "vat_return" / "vat_return.js",
			DOCTYPES / "recapitulative_statement" / "recapitulative_statement.js",
		):
			with self.subTest(script=script.name):
				self.assertIn("has_vat_ids_to_confirm(frm)", read(script))
		self.assertIn('"numbers": []', read(CONFIRMING))

	def test_the_methods_the_forms_call_are_whitelisted_for_post(self):
		source = read(PARTNERS)
		for method in ("confirm_vat_id", "confirm_invoice_customer"):
			with self.subTest(method=method):
				self.assertRegex(source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\ndef {method}\(')
		self.assertIn("confirm_invoice_customer", read(INVOICE_SCRIPT))

	def test_every_trigger_asks_the_one_rule_of_who_may_ask(self):
		source = read(PARTNERS)
		self.assertIn("if not may_ask(*(source or (party_type, party)), throw=throw):", source)
		self.assertIn('"can_ask": number_kind.sent and may_ask(party_type, party)', source)
		self.assertNotIn("check_permission(", source)


class TranslationFilesTest(TestCase):
	def test_every_text_reads_in_german(self):
		texts = set()
		for path in (PARTNERS, SETUP, REPORT / f"{REPORT.name}.py", CONFIRMING):
			texts |= python_texts(path)
		texts |= set(literal(SETUP, "MESSAGES"))
		texts |= {value for value in literal(PARTNERS, "STATUSES") if value}
		texts |= set(literal(PARTNERS, "TRIGGERS"))
		texts |= set(literal(REPORT / f"{REPORT.name}.py", "STANDING_NOTES").values())
		texts.add(literal(REPORT / f"{REPORT.name}.py", "NO_REQUESTER"))
		texts |= {standing.value for standing in Standing}
		texts |= {level.value for level in Level}
		texts |= {step["label"] for step in hooks.steuerbote_setup_steps}
		for path in (PARTNER_SCRIPT, INVOICE_SCRIPT, SHARED_SCRIPT, REPORT / f"{REPORT.name}.js"):
			texts |= set(JS_TRANSLATED.findall(read(path)))
		fields = custom_fields()
		for key in [(doctype, name) for doctype in ("Customer", "Supplier") for name in PARTY_FIELDS] + [
			("Sales Invoice", name) for name in INVOICE_FIELDS
		]:
			texts |= {fields[key]["label"]} | (
				{fields[key]["description"]} if fields[key].get("description") else set()
			)
		for doctype, names in (
			("vat_return_settings", None),
			("vat_id_confirmation", ("party_type", "party", "sales_invoice", "started_by")),
		):
			for name, field in fields_of(doctype).items():
				if (names is None and (name.startswith("vat_id_") or name == "max_confirmation_age")) or (
					names and name in names
				):
					texts |= {field.get("label")} | (
						{field["description"]} if field.get("description") else set()
					)
		texts.discard(None)
		german = translations()
		self.assertEqual(sorted(texts - german.keys() - FRAMEWORK), [])
		self.assertEqual(german["VAT ID"], "USt-IdNr.")
		self.assertEqual(german["Open VAT IDs"], "Offene USt-IdNrn.")
