"""The files of the Annual VAT Return, read without a bench: its DocTypes with the standard fields of an annual
document, the tables the bridge writes and the German of their texts."""

import csv
import json
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from steuerbote.jahresmeldung.lifecycle import FILING, field_problems
from steuerbote.steuerbote.doctype.annual_vat_return import bridge
from steuerbote.steuerbote.doctype.vat_return_settings.rules import FilingRhythm, PeriodRule
from steuerbote.ustjahr import calculation, reconciliation, rules, soll
from steuerbote.ustjahr.calculation import calculate
from steuerbote.ustjahr.reconciliation import reconcile
from steuerbote.ustjahr.soll import vorauszahlungssoll
from steuerbote.ustjahr.split import split
from steuerbote.ustva import calculate as calculate_ustva
from steuerbote.ustva.calculation import LedgerLine
from steuerbote.ustva.mapping import AccountRule, Mapping, Side

APP = Path(__file__).resolve().parents[3]
MODULE = APP / "steuerbote"
DOCTYPES = MODULE / "doctype"
DIRECTORY = DOCTYPES / "annual_vat_return"
TRANSLATIONS = APP / "translations" / "de.csv"
CHILDREN = (
	"annual_vat_return_line",
	"annual_vat_return_period",
	"annual_vat_return_reconciliation",
	"annual_vat_return_property",
)
# Labels Frappe and ERPNext translate themselves (frappe/locale/de.po and erpnext/locale/de.po of version 16), and
# terms that read the same in German; the app keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{"Amended From", "Description", "Difference", "Due Date", "Fiscal Year", "From Date", "Remarks"}
	| {"Series", "Status", "To Date"}
)
UNTRANSLATED = frozenset({"Kz 39", "Kz 83", "Transferticket", "Verprobung"})


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def definition(name: str = "annual_vat_return") -> dict:
	return read_json(DOCTYPES / name / f"{name}.json")


def fields_of(name: str = "annual_vat_return") -> dict[str, dict]:
	return {field["fieldname"]: field for field in definition(name)["fields"]}


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def example_rows() -> dict[str, list[dict]]:
	"""The rows Berechnen writes for a small year: a sale in the first quarter, and no Voranmeldung filed."""
	mapping = Mapping("SKR03", (AccountRule("8400", "81", Side.CREDIT),))
	quarters = bridge.year_periods([PeriodRule(2026, FilingRhythm.QUARTERLY)], 2026)
	lines = [LedgerLine("8400", Decimal("0"), Decimal("1000"), "Sales Invoice:R1")]
	result = calculate(lines, split(mapping))
	found = vorauszahlungssoll(2026, (), bridge.due_periods(quarters))
	now = {
		entry.period: calculate_ustva(lines if entry.period.index == 1 else [], mapping) for entry in quarters
	}
	recon = reconcile(result, found, now)
	return {
		"lines": bridge.line_rows(result),
		"periods": bridge.period_rows(quarters, recon, {}),
		"reconciliation": bridge.reconciliation_rows(recon, 2026),
	}


class DocTypeFilesTest(TestCase):
	def setUp(self):
		self.definition = definition()
		self.fields = fields_of()

	def test_has_the_standard_fields_of_an_annual_document_that_goes_to_elster(self):
		self.assertEqual(field_problems(self.definition, FILING, transmits=True), [])

	def test_is_numbered_by_the_year_of_the_return(self):
		self.assertEqual(
			(self.definition["name"], self.definition["autoname"], self.definition["is_submittable"]),
			("Annual VAT Return", "naming_series:", 1),
		)
		series = self.fields["naming_series"]
		self.assertEqual((series["options"], series["default"]), ("UStE-.{year}.-.#####",) * 2)

	def test_its_permissions_are_those_of_the_vat_return(self):
		vat_return = definition("vat_return")
		self.assertEqual(self.definition["permissions"], vat_return["permissions"])

	def test_the_field_order_names_every_field_once(self):
		for name in ("annual_vat_return", *CHILDREN):
			with self.subTest(doctype=name):
				record = definition(name)
				self.assertEqual(record["field_order"], [field["fieldname"] for field in record["fields"]])
				self.assertEqual(record["module"], "Steuerbote")

	def test_the_tables_take_their_child_doctypes(self):
		self.assertEqual(
			{
				name: self.fields[name]["options"]
				for name in ("lines", "periods", "reconciliation", "properties")
			},
			{
				"lines": "Annual VAT Return Line",
				"periods": "Annual VAT Return Period",
				"reconciliation": "Annual VAT Return Reconciliation",
				"properties": "Annual VAT Return Property",
			},
		)
		self.assertEqual(
			{name: self.fields[name]["options"] for name in ("checks", "deviations", "unmapped")},
			{
				"checks": "VAT Return Check",
				"deviations": "VAT Return Deviation",
				"unmapped": "VAT Return Unmapped Account",
			},
		)
		for name in CHILDREN:
			with self.subTest(doctype=name):
				self.assertEqual(definition(name)["istable"], 1)

	def test_the_periods_take_the_reasons_alone_and_no_row_by_hand(self):
		periods = self.fields["periods"]
		self.assertEqual((periods.get("cannot_add_rows"), periods.get("cannot_delete_rows")), (1, 1))
		editable = [
			field["fieldname"]
			for field in definition("annual_vat_return_period")["fields"]
			if not field.get("read_only") and field["fieldtype"] != "Column Break"
		]
		self.assertEqual(editable, ["waiver_reason"])

	def test_the_lines_hold_the_columns_of_the_base(self):
		fields = fields_of("annual_vat_return_line")
		columns = bridge.LINE_COLUMNS
		self.assertEqual(
			sorted(
				{
					columns.key,
					*columns.amounts,
					*columns.described,
					columns.correction,
					columns.reason,
					columns.reported,
					columns.manual,
				}
				- set(fields)
			),
			[],
		)
		editable = sorted(
			name
			for name, field in fields.items()
			if not field.get("read_only") and field["fieldtype"] != "Column Break"
		)
		self.assertEqual(editable, ["correction", "correction_reason", "feldkennung", "paragraph"])
		for name in ("feldkennung", "paragraph"):
			with self.subTest(field=name):
				self.assertEqual(fields[name]["read_only_depends_on"], "eval:!doc.manual")

	def test_the_tables_hold_the_rows_the_bridge_writes(self):
		for table, rows in example_rows().items():
			child = {
				"lines": "annual_vat_return_line",
				"periods": "annual_vat_return_period",
				"reconciliation": "annual_vat_return_reconciliation",
			}[table]
			with self.subTest(table=table):
				self.assertTrue(rows)
				self.assertEqual(sorted({key for row in rows for key in row} - set(fields_of(child))), [])

	def test_the_cause_offers_what_the_bridge_writes(self):
		options = fields_of("annual_vat_return_period")["cause"]["options"].split("\n")
		self.assertEqual(options, ["", *bridge.CAUSES.values()])

	def test_the_grundstuecke_hold_the_columns_of_line_95(self):
		self.assertEqual(list(fields_of("annual_vat_return_property")), list(bridge.GRUNDSTUECK_FIELDS))

	def test_the_grids_show_at_most_ten_columns(self):
		for name in CHILDREN:
			with self.subTest(doctype=name):
				listed = [field for field in definition(name)["fields"] if field.get("in_list_view")]
				self.assertLessEqual(sum(field.get("columns", 0) for field in listed), 10)

	def test_the_money_takes_the_currency_of_the_company(self):
		for name in ("annual_vat_return", *CHILDREN):
			for field in definition(name)["fields"]:
				if field["fieldtype"] == "Currency":
					with self.subTest(doctype=name, field=field["fieldname"]):
						self.assertEqual(field["options"], "Company:company:default_currency")

	def test_the_return_shows_its_elster_transmissions(self):
		source = (DIRECTORY / "annual_vat_return_dashboard.py").read_text(encoding="utf-8")
		self.assertIn('return dashboard("Annual VAT Return")', source)


def texts_of_the_doctypes() -> set[str]:
	texts = set()
	for name in ("annual_vat_return", *CHILDREN):
		record = definition(name)
		texts.update(text for text in (record["name"], record.get("description")) if text)
		for field in record["fields"]:
			texts.update(field[key] for key in ("label", "description") if field.get(key))
			if field["fieldtype"] == "Select" and field["fieldname"] not in (
				"naming_series",
				"status",
				"filed_via",
				"kz500",
			):
				texts.update(option for option in field["options"].split("\n") if option)
	return texts


def messages_of_the_core() -> set[str]:
	"""What the core of the annual return and the bridge report, which the Frappe layer translates."""
	return {
		*bridge.MESSAGES,
		*calculation.MESSAGES,
		*soll.MESSAGES,
		*reconciliation.MESSAGES,
		*rules.MESSAGES,
	}


class TranslationsFilesTest(TestCase):
	def test_every_text_of_the_doctypes_is_translated(self):
		missing = texts_of_the_doctypes() - set(translations()) - FRAMEWORK_LABELS - UNTRANSLATED
		self.assertEqual(sorted(missing), [])

	def test_every_message_of_the_core_is_translated(self):
		self.assertEqual(sorted(messages_of_the_core() - set(translations())), [])

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & set(translations())), [])

	def test_the_return_reads_as_the_law_names_it(self):
		german = translations()
		self.assertEqual(german["Annual VAT Return"], "Umsatzsteuererklärung")
		self.assertEqual(german["Vorauszahlungssoll (Line 125)"], "Vorauszahlungssoll (Zeile 125)")
