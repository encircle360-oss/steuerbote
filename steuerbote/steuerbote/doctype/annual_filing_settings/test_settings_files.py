"""The DocTypes of the Annual Filing Settings fit their rules, read from their files without a bench."""

import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.elster import STATES
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import (
	ROW_TEXT_LENGTHS,
	TEXT_LENGTHS,
	CarryForwardKind,
	LegalForm,
	ShareholderKind,
	SizeClass,
	Tax,
)

DOCTYPE_DIR = Path(__file__).resolve().parents[1]
SETTINGS = DOCTYPE_DIR / "annual_filing_settings"
ARCHITECTURE = Path(__file__).resolve().parents[4] / "docs" / "architektur.md"
LAYOUT = frozenset({"Section Break", "Column Break"})
# The numbers of natural persons, which only the Körperschaftsteuererklärung may carry (§ 139b Abs. 2 AO).
IDENTIFIERS = ("tax_number_state", "tax_number", "idnr", "wid_nr", "foreign_id")


def read(name: str) -> dict:
	return json.loads((DOCTYPE_DIR / name / f"{name}.json").read_text(encoding="utf-8"))


def fields(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in read(name)["fields"]}


def options(name: str, fieldname: str) -> list[str]:
	return fields(name)[fieldname]["options"].split("\n")


class SettingsFilesTest(TestCase):
	def setUp(self):
		self.settings = read("annual_filing_settings")
		self.fields = fields("annual_filing_settings")

	def test_one_document_per_company_of_the_module(self):
		self.assertEqual(
			{key: self.settings[key] for key in ("name", "module", "autoname", "naming_rule")},
			{
				"name": "Annual Filing Settings",
				"module": "Steuerbote",
				"autoname": "field:company",
				"naming_rule": "By fieldname",
			},
		)
		company = self.fields["company"]
		self.assertEqual((company["options"], company["reqd"], company["unique"]), ("Company", 1, 1))

	def test_accounts_managers_and_system_managers_change_the_settings_and_accounts_users_read_them(self):
		"""As the VAT Return Settings: what the settings say goes to the Finanzamt with every filing."""
		self.assertEqual(
			self.settings["permissions"],
			[
				{
					"create": 1,
					"delete": 1,
					"email": 1,
					"export": 1,
					"print": 1,
					"read": 1,
					"report": 1,
					"role": "System Manager",
					"share": 1,
					"write": 1,
				},
				{"permlevel": 1, "read": 1, "role": "System Manager", "write": 1},
				{"create": 1, "read": 1, "role": "Accounts Manager", "write": 1},
				{"permlevel": 1, "read": 1, "role": "Accounts Manager", "write": 1},
				{"read": 1, "role": "Accounts User"},
			],
		)

	def test_only_the_numbers_of_the_shareholders_have_permlevel_1(self):
		raised = {
			(name, field["fieldname"])
			for name in [path.name for path in sorted(DOCTYPE_DIR.glob("annual_filing_*"))]
			for field in read(name)["fields"]
			if field.get("permlevel")
		}
		self.assertEqual(
			raised,
			{("annual_filing_shareholder", fieldname) for fieldname in IDENTIFIERS}
			| {
				("annual_filing_shareholder", "identifiers_section"),
				("annual_filing_shareholder", "column_break_identifiers"),
			},
		)

	def test_the_numbers_of_the_shareholders_are_neither_listed_searched_nor_logged(self):
		"""A version of the document would keep every row as it was, numbers included, for anyone who reads it."""
		self.assertEqual(self.settings["track_changes"], 0)
		shareholder = read("annual_filing_shareholder")
		self.assertNotIn("search_fields", shareholder)
		for fieldname in IDENTIFIERS:
			field = fields("annual_filing_shareholder")[fieldname]
			with self.subTest(fieldname=fieldname):
				for key in ("in_list_view", "in_standard_filter", "in_global_search", "unique", "bold"):
					self.assertFalse(field.get(key))

	def test_the_options_are_those_of_the_rules(self):
		self.assertEqual(options("annual_filing_settings", "legal_form"), ["", *LegalForm])
		self.assertEqual(options("annual_filing_shareholder", "kind"), list(ShareholderKind))
		self.assertEqual(options("annual_filing_shareholder", "tax_number_state"), ["", *STATES.values()])
		self.assertEqual(options("annual_filing_prepayment", "tax"), list(Tax))
		self.assertEqual(options("annual_filing_carry_forward", "kind"), list(CarryForwardKind))
		self.assertEqual(options("annual_filing_size_class", "size_class"), list(SizeClass))
		self.assertEqual(
			options("annual_filing_settings", "register_type"), ["", "HRA", "HRB", "GnR", "PR", "VR"]
		)

	def test_the_fields_take_the_lengths_of_the_forms(self):
		self.assertEqual({name: self.fields[name]["length"] for name in TEXT_LENGTHS}, dict(TEXT_LENGTHS))
		for table, lengths in ROW_TEXT_LENGTHS.items():
			child = fields(self.fields[table]["options"].lower().replace(" ", "_"))
			for fieldname in lengths:
				with self.subTest(table=table, fieldname=fieldname):
					self.assertIn(fieldname, child)
		self.assertEqual(fields("annual_filing_establishment")["hebenummer"]["length"], 28)
		self.assertEqual(self.fields["house_number"]["length"], 4)

	def test_every_table_is_a_child_doctype_of_the_settings(self):
		tables = {field["options"] for field in self.fields.values() if field["fieldtype"] == "Table"}
		children = {
			read(path.name)["name"]
			for path in DOCTYPE_DIR.glob("annual_filing_*")
			if read(path.name).get("istable")
		}
		self.assertEqual(tables, children)
		self.assertEqual(len(tables), 10)

	def test_the_field_order_names_every_field_once(self):
		for path in sorted(DOCTYPE_DIR.glob("annual_filing_*")):
			definition = read(path.name)
			with self.subTest(doctype=definition["name"]):
				self.assertEqual(
					definition["field_order"], [field["fieldname"] for field in definition["fields"]]
				)
				self.assertEqual(len(set(definition["field_order"])), len(definition["field_order"]))

	def test_only_the_jahresabschluss_writes_the_day_of_its_feststellung(self):
		self.assertEqual(fields("annual_filing_year")["adopted_on"].get("read_only"), 1)
		self.assertEqual(self.fields["elster_income_tax_number"].get("read_only"), 1)

	def test_the_methods_the_form_calls_are_whitelisted_for_post(self):
		script = (SETTINGS / "annual_filing_settings.js").read_text(encoding="utf-8")
		source = (SETTINGS / "annual_filing_settings.py").read_text(encoding="utf-8")
		methods = sorted(set(re.findall(r'frm\.call\("(\w+)"', script)))
		self.assertEqual(methods, ["fill_address"])
		for method in methods:
			with self.subTest(method=method):
				self.assertRegex(source, rf'@frappe\.whitelist\(methods=\["POST"\]\)\n\tdef {method}\(')

	def test_the_architecture_describes_every_field_of_the_settings(self):
		text = ARCHITECTURE.read_text(encoding="utf-8")
		start = text.index("### Einstellungen Jahresmeldungen (`Annual Filing Settings`)")
		section = text[start : text.index("\n### ", start + 1)]
		described = {
			name
			for line in section.splitlines()
			if line.startswith("| `")
			for name in re.findall(r"`(\w+)`", line.split(" | ")[0])
		}
		data_fields = {name for name, field in self.fields.items() if field["fieldtype"] not in LAYOUT}
		self.assertEqual(described, data_fields)
