"""The DocTypes of the E-Bilanz, read without a bench: the standard fields of an annual document, its child tables with
the rows the bridge writes and the options the bridge reads, and the German of their texts and of the messages of the
bridge and of the report. test_electronic_balance_sheet_site_files.py reads the controller, the form script, the print
format and the report."""

import csv
import json
import re
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from steuerbote.ebilanz.positions import AccountingStandard, Mark
from steuerbote.jahresmeldung.corrections import BY_THE_TAX_ADMINISTRATION, RevisionStatus
from steuerbote.jahresmeldung.lifecycle import FILING, field_problems
from steuerbote.steuerbote.doctype.electronic_balance_sheet import bridge
from steuerbote.steuerbote.doctype.electronic_balance_sheet.test_bridge import ebilanz
from steuerbote.steuerbote.report.e_bilanz_positionen import rows as report_rows
from steuerbote.xbrl.versions import TAXONOMIES

APP = Path(__file__).resolve().parents[3]
MODULE = APP / "steuerbote"
DOCTYPES = MODULE / "doctype"
NAME = "electronic_balance_sheet"
CHILDREN = (
	"electronic_balance_sheet_position",
	"electronic_balance_sheet_account",
	"electronic_balance_sheet_fixed_asset",
	"electronic_balance_sheet_transfer",
)
ALL = (NAME, *CHILDREN)
TRANSLATIONS = APP / "translations" / "de.csv"
PLACEHOLDER = re.compile(r"\{\d*\}")
# Labels Frappe and ERPNext translate themselves (frappe/locale/de.po and erpnext/locale/de.po of version 16); the app
# keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{"Amended From", "Asset Category", "Calculated Amount", "Currency", "Depreciation", "Description"}
	| {"Due Date", "Fiscal Year", "From Date", "Level", "Position", "Reason", "Remarks", "Series", "Status"}
	| {"To Date", "Totals"}
)
# Terms that read the same in German.
UNTRANSLATED = frozenset(
	{
		"Anlagenspiegel",
		"Betriebsvermögensvergleich",
		"Eröffnungsbilanz",
		"Jahresabschluss",
		"Kapitalanpassung",
	}
	| {"NIL", "Transferticket", "Überleitungsrechnung", "Umgliederung", "Umgliederung und Wertänderung"}
	| {"Wertänderung"}
)
# The codes and the states of the lifecycle are filed or shown as they are: the naming series, the status, the way of
# the filing, the Status des Berichts, the Bilanzierungsstandard, the version of the taxonomy, the component, the mark
# and the value type of the taxonomy.
UNTRANSLATED_SELECTS = frozenset(
	{"naming_series", "status", "filed_via", "revision_status", "accounting_standard", "taxonomy_version"}
	| {"component", "mark", "value_type"}
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


class DocTypeFilesTest(TestCase):
	def test_has_the_standard_fields_of_an_annual_document_that_goes_to_elster(self):
		self.assertEqual(field_problems(definition(NAME), FILING, transmits=True), [])

	def test_is_numbered_by_the_year_of_the_e_bilanz(self):
		record = definition(NAME)
		self.assertEqual(
			(record["name"], record["autoname"], record["is_submittable"]),
			("Electronic Balance Sheet", "naming_series:", 1),
		)
		series = fields_of(NAME)["naming_series"]
		self.assertEqual((series["options"], series["default"]), ("EB-.{year}.-.#####",) * 2)

	def test_its_permissions_are_those_of_the_vat_return(self):
		self.assertEqual(definition(NAME)["permissions"], definition("vat_return")["permissions"])

	def test_the_field_order_names_every_field_once(self):
		for name in ALL:
			with self.subTest(doctype=name):
				record = definition(name)
				self.assertEqual(record["field_order"], [field["fieldname"] for field in record["fields"]])
				self.assertEqual(record["module"], "Steuerbote")

	def test_the_tables_take_their_child_doctypes(self):
		fields = fields_of(NAME)
		tables = {
			"positions": "Electronic Balance Sheet Position",
			"fixed_assets": "Electronic Balance Sheet Fixed Asset",
			"transfers": "Electronic Balance Sheet Transfer",
			"accounts": "Electronic Balance Sheet Account",
			"findings": "Annual Filing Finding",
		}
		self.assertEqual({table: fields[table]["options"] for table in tables}, tables)
		for name in CHILDREN:
			with self.subTest(doctype=name):
				self.assertEqual(
					(definition(name)["istable"], definition(name)["name"]), (1, tables_of(name))
				)
		self.assertEqual((fields["accounts"]["read_only"], fields["findings"]["read_only"]), (1, 1))

	def test_the_positions_hold_the_columns_of_the_base(self):
		fields = fields_of("electronic_balance_sheet_position")
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
		self.assertEqual(
			sorted(
				fieldname
				for fieldname, field in fields.items()
				if not field.get("read_only") and field["fieldtype"] != "Column Break"
			),
			["concept", "correction", "correction_reason"],
		)
		self.assertEqual(fields["concept"]["read_only_depends_on"], "eval:!doc.manual")

	def test_the_tables_hold_the_rows_the_bridge_writes(self):
		found = ebilanz()
		structure = found.structure
		fixed = bridge.fixed_asset_rows(
			structure,
			bridge.category_rows(
				[bridge.CategoryValues("Software", "0135", Decimal("15000.00"))],
				{"0135": "bs.ass.fixAss.intan.concessionBrands"},
				"StB",
			),
		)
		transfers = bridge.labelled_transfers(
			structure,
			bridge.transfer_rows((), [{"kind": "Wertänderung", "position": "bs.ass", "current": 1}]),
		)
		for child, written in (
			("electronic_balance_sheet_position", bridge.position_rows(found)),
			("electronic_balance_sheet_account", bridge.account_rows(found)),
			("electronic_balance_sheet_fixed_asset", fixed),
			("electronic_balance_sheet_transfer", transfers),
		):
			with self.subTest(table=child):
				self.assertTrue(written)
				self.assertEqual(sorted({key for row in written for key in row} - set(fields_of(child))), [])

	def test_the_options_are_those_the_bridge_reads(self):
		for name, fieldname, options in (
			(NAME, "statement_type", list(bridge.STATEMENT_TYPES)),
			(NAME, "accounting_standard", [standard.value for standard in AccountingStandard]),
			(NAME, "taxonomy_version", list(TAXONOMIES)),
			("electronic_balance_sheet_fixed_asset", "value_type", list(bridge.VALUE_TYPES)),
			("electronic_balance_sheet_transfer", "kind", list(bridge.TRANSFER_KINDS)),
			("electronic_balance_sheet_position", "component", ["", *bridge.COMPONENTS]),
			("electronic_balance_sheet_position", "mark", ["", *(mark.value for mark in Mark if mark.value)]),
		):
			with self.subTest(doctype=name, field=fieldname):
				self.assertEqual(options_of(name, fieldname), options)

	def test_the_status_des_berichts_takes_no_korrektur_durch_finanzverwaltung(self):
		"""FAQ zur E-Bilanz, Version 2026-01, Tz. 4 d; Steuerbote sets erstmalig itself."""
		options = options_of(NAME, "revision_status")
		self.assertEqual(options, ["", *(status.value for status in RevisionStatus)])
		self.assertNotIn(BY_THE_TAX_ADMINISTRATION, options)
		self.assertEqual(fields_of(NAME)["revision_status"]["depends_on"], "eval:doc.is_correction")

	def test_the_betriebsvermoegensvergleich_and_the_ueberleitung_show_where_they_count(self):
		fields = fields_of(NAME)
		self.assertEqual(fields["bvv_section"]["depends_on"], "eval:doc.statement_type==='Jahresabschluss'")
		self.assertEqual(fields["transfers_section"]["depends_on"], "eval:doc.accounting_standard==='HGBM'")
		self.assertEqual(fields["commercial_finance_book"]["options"], "Finance Book")
		self.assertEqual(fields["tax_finance_book"]["options"], "Finance Book")

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


def tables_of(name: str) -> str:
	return {
		"electronic_balance_sheet_position": "Electronic Balance Sheet Position",
		"electronic_balance_sheet_account": "Electronic Balance Sheet Account",
		"electronic_balance_sheet_fixed_asset": "Electronic Balance Sheet Fixed Asset",
		"electronic_balance_sheet_transfer": "Electronic Balance Sheet Transfer",
	}[name]


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


def messages_of_the_bridge() -> set[str]:
	"""What the bridge and the report give the Frappe layer to translate."""
	return {*bridge.MESSAGES, *bridge.TABLES, *report_rows.MESSAGES}


class TranslationsFilesTest(TestCase):
	def test_the_sources_are_read(self):
		for text, found in (
			("Electronic Balance Sheet", texts_of_the_doctypes()),
			("Adjustments by ERPNext", texts_of_the_doctypes()),
			(bridge.DOUBLED, messages_of_the_bridge()),
			(report_rows.NOT_FILED, messages_of_the_bridge()),
		):
			with self.subTest(text=text):
				self.assertIn(text, found)

	def test_every_text_of_the_doctypes_is_translated(self):
		missing = texts_of_the_doctypes() - set(translations()) - FRAMEWORK_LABELS - UNTRANSLATED
		self.assertEqual(sorted(missing), [])

	def test_every_message_of_the_bridge_and_the_report_is_translated(self):
		self.assertEqual(sorted(messages_of_the_bridge() - set(translations()) - UNTRANSLATED), [])

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & set(translations())), [])

	def test_the_translations_keep_the_placeholders(self):
		german = translations()
		for text in messages_of_the_bridge() - UNTRANSLATED:
			with self.subTest(text=text):
				self.assertCountEqual(PLACEHOLDER.findall(german[text]), PLACEHOLDER.findall(text))

	def test_the_e_bilanz_reads_as_the_law_names_it(self):
		"""§ 5b EStG: „Elektronische Übermittlung von Bilanzen sowie Gewinn- und Verlustrechnungen“."""
		german = translations()
		self.assertEqual(german["Electronic Balance Sheet"], "E-Bilanz")
		self.assertEqual(german["Kind of Balance Sheet"], "Bilanzart")
		self.assertEqual(german["Status of the Report"], "Status des Berichts")
