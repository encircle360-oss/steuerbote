"""The DocTypes of the Körperschaftsteuer- and the Gewerbesteuererklärung, read without a bench: the standard fields of
an annual document, their child tables with the rows the bridges write and the options the bridges read, and the
German of their texts and of the messages of the bridges. test_income_tax_site_files.py reads the controllers, the form
scripts, the print formats and the report."""

import csv
import json
import re
from pathlib import Path
from unittest import TestCase

from steuerbote.jahresmeldung.lifecycle import FILING, field_problems
from steuerbote.steuerbote.doctype.annual_filing_settings.rules import CarryForwardKind
from steuerbote.steuerbote.doctype.corporate_income_tax_return import bridge
from steuerbote.steuerbote.doctype.corporate_income_tax_return import test_bridge as corporate
from steuerbote.steuerbote.doctype.trade_tax_return import bridge as trade_bridge
from steuerbote.steuerbote.doctype.trade_tax_return import test_bridge as trade
from steuerbote.steuerbote.report.ertragsteuer_kontennachweis import attribution

APP = Path(__file__).resolve().parents[3]
MODULE = APP / "steuerbote"
DOCTYPES = MODULE / "doctype"
KST = "corporate_income_tax_return"
GEWST = "trade_tax_return"
KST_CHILDREN = (
	"corporate_income_tax_return_line",
	"corporate_income_tax_return_holding_result",
	"corporate_income_tax_return_credit",
	"corporate_income_tax_return_donation",
	"corporate_income_tax_return_distribution",
	"corporate_income_tax_return_contribution",
)
GEWST_CHILDREN = ("trade_tax_return_line", "trade_tax_return_municipality", "trade_tax_return_holding")
ALL = (KST, *KST_CHILDREN, GEWST, *GEWST_CHILDREN)
TRANSLATIONS = APP / "translations" / "de.csv"
PLACEHOLDER = re.compile(r"\{\d*\}")
# Labels Frappe and ERPNext translate themselves (frappe/locale/de.po and erpnext/locale/de.po of version 16); the app
# keeps out of their translations.
FRAMEWORK_LABELS = frozenset(
	{"Amended From", "Amount", "Credit", "Currency", "Debit", "Description", "Due Date", "Fiscal Year"}
	| {"From Date", "Posting Date", "Recipient", "Remarks", "Series", "Shareholder", "Status", "To Date"}
	| {"Voucher No", "Voucher Type"}
)
# Terms that read the same in German.
UNTRANSLATED = frozenset(
	{"Amtlicher Gemeindeschlüssel", "Anlagen BEG", "Gemeinde", "Gewerbesteuer", "Hebenummer", "Hebesatz"}
	| {
		"Kapitalertragsteuer",
		"Solidaritätszuschlag",
		"Steuerliches Einlagekonto (KSt 1 F)",
		"Steuermessbetrag",
	}
	| {"Transferticket", "Verlustrücktrag", "Vorauszahlungen", "Vorgang"}
)
# The keys of the Listenfelder, the codes of the Vordrucke and the states of the lifecycle are filed or shown as they
# are.
UNTRANSLATED_SELECTS = frozenset({"naming_series", "status", "filed_via", "supplement_key", "form"})


def read_json(path: Path) -> dict:
	return json.loads(path.read_text(encoding="utf-8"))


def definition(name: str) -> dict:
	return read_json(DOCTYPES / name / f"{name}.json")


def fields_of(name: str) -> dict[str, dict]:
	return {field["fieldname"]: field for field in definition(name)["fields"]}


def translations() -> dict[str, str]:
	with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
		return dict(csv.reader(file))


def gewst_computation():
	return trade.compute()


class DocTypeFilesTest(TestCase):
	def test_have_the_standard_fields_of_an_annual_document_that_goes_to_elster(self):
		for name in (KST, GEWST):
			with self.subTest(doctype=name):
				self.assertEqual(field_problems(definition(name), FILING, transmits=True), [])

	def test_are_numbered_by_the_year_of_the_return(self):
		for name, label, prefix in (
			(KST, "Corporate Income Tax Return", "KSt"),
			(GEWST, "Trade Tax Return", "GewSt"),
		):
			with self.subTest(doctype=name):
				record = definition(name)
				self.assertEqual(
					(record["name"], record["autoname"], record["is_submittable"]),
					(label, "naming_series:", 1),
				)
				series = fields_of(name)["naming_series"]
				self.assertEqual((series["options"], series["default"]), (f"{prefix}-.{{year}}.-.#####",) * 2)

	def test_their_permissions_are_those_of_the_vat_return(self):
		for name in (KST, GEWST):
			with self.subTest(doctype=name):
				self.assertEqual(definition(name)["permissions"], definition("vat_return")["permissions"])

	def test_the_field_order_names_every_field_once(self):
		for name in ALL:
			with self.subTest(doctype=name):
				record = definition(name)
				self.assertEqual(record["field_order"], [field["fieldname"] for field in record["fields"]])
				self.assertEqual(record["module"], "Steuerbote")

	def test_the_tables_take_their_child_doctypes(self):
		for name, tables in (
			(
				KST,
				{
					"lines": "Corporate Income Tax Return Line",
					"holding_results": "Corporate Income Tax Return Holding Result",
					"credits": "Corporate Income Tax Return Credit",
					"donations": "Corporate Income Tax Return Donation",
					"distributions": "Corporate Income Tax Return Distribution",
					"contributions": "Corporate Income Tax Return Contribution",
					"findings": "Annual Filing Finding",
				},
			),
			(
				GEWST,
				{
					"lines": "Trade Tax Return Line",
					"municipalities": "Trade Tax Return Municipality",
					"holdings": "Trade Tax Return Holding",
					"donations": "Corporate Income Tax Return Donation",
					"findings": "Annual Filing Finding",
				},
			),
		):
			fields = fields_of(name)
			with self.subTest(doctype=name):
				self.assertEqual({table: fields[table]["options"] for table in tables}, tables)
		for name in (*KST_CHILDREN, *GEWST_CHILDREN):
			with self.subTest(doctype=name):
				self.assertEqual(definition(name)["istable"], 1)
		self.assertEqual(
			fields_of(GEWST)["corporate_income_tax_return"]["options"], "Corporate Income Tax Return"
		)

	def test_the_lines_hold_the_columns_of_the_base(self):
		for name, columns, editable in (
			(
				"corporate_income_tax_return_line",
				bridge.LINE_COLUMNS,
				["correction", "correction_reason", "feldkennung"],
			),
			("trade_tax_return_line", trade_bridge.LINE_COLUMNS, []),
		):
			fields = fields_of(name)
			with self.subTest(doctype=name):
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
					editable,
				)
		feldkennung = fields_of("corporate_income_tax_return_line")["feldkennung"]
		self.assertEqual(feldkennung["read_only_depends_on"], "eval:!doc.manual")
		self.assertEqual(
			fields_of("corporate_income_tax_return_line")["form"]["options"].split("\n"),
			["KSt1", *bridge.FORMS_OF_LINES],
		)

	def test_the_tables_hold_the_rows_the_bridges_write(self):
		computation = gewst_computation()
		for child, rows in (
			("corporate_income_tax_return_line", corporate.compute().lines),
			("trade_tax_return_line", computation.lines),
			("trade_tax_return_municipality", computation.municipalities),
			("trade_tax_return_holding", computation.holdings),
		):
			with self.subTest(table=child):
				self.assertTrue(rows)
				self.assertEqual(sorted({key for row in rows for key in row} - set(fields_of(child))), [])

	def test_the_options_are_those_the_bridge_reads(self):
		for child, fieldname, options in (
			("corporate_income_tax_return_holding_result", "kind", bridge.HOLDING_KINDS),
			("corporate_income_tax_return_distribution", "kind", tuple(bridge.DISTRIBUTION_KINDS)),
			("corporate_income_tax_return_contribution", "treatment", bridge.CONTRIBUTION_TREATMENTS),
			("corporate_income_tax_return_contribution", "kind", tuple(bridge.CONTRIBUTION_KINDS)),
		):
			with self.subTest(table=child, field=fieldname):
				self.assertEqual(tuple(fields_of(child)[fieldname]["options"].split("\n")), options)
		self.assertEqual(
			fields_of(KST)["supplement_key"]["options"].split("\n"), ["", *bridge.SUPPLEMENT_KEYS]
		)
		self.assertEqual(
			fields_of(GEWST)["supplement_key"]["options"].split("\n"), ["", *bridge.SUPPLEMENT_KEYS]
		)

	def test_a_sale_names_its_price_costs_book_value_and_day(self):
		fields = fields_of("corporate_income_tax_return_holding_result")
		for fieldname in ("sale_price", "sale_costs", "book_value", "result_date"):
			with self.subTest(field=fieldname):
				self.assertEqual(fields[fieldname]["depends_on"], "eval:doc.kind == 'Sale'")
		self.assertEqual(fields["result_date"]["mandatory_depends_on"], "eval:doc.kind == 'Sale'")
		self.assertEqual(fields["amount"]["read_only_depends_on"], "eval:doc.kind == 'Sale'")
		self.assertEqual(fields["amount"]["mandatory_depends_on"], "eval:doc.kind != 'Sale'")
		for fieldname in ("percent_on_1_january", "percent_at_start_of_ez", "exemption"):
			with self.subTest(field=fieldname):
				self.assertEqual(fields[fieldname]["read_only"], 1)

	def test_a_leistung_and_an_einlage_carry_their_day(self):
		self.assertEqual(fields_of("corporate_income_tax_return_distribution")["outflow_date"]["reqd"], 1)
		self.assertEqual(
			fields_of("corporate_income_tax_return_distribution")["resolution_date"]["mandatory_depends_on"],
			f"eval:doc.kind == '{bridge.ORDINARY}'",
		)
		self.assertEqual(
			fields_of("corporate_income_tax_return_contribution")["contribution_date"]["reqd"], 1
		)

	def test_the_qualified_free_text_goes_with_its_key(self):
		for name in (KST, GEWST):
			fields = fields_of(name)
			with self.subTest(doctype=name):
				self.assertEqual(fields["supplement_key"]["mandatory_depends_on"], "eval:doc.supplement_text")
				self.assertEqual(fields["supplement_text"]["mandatory_depends_on"], "eval:doc.supplement_key")

	def test_the_grids_show_at_most_ten_columns(self):
		for name in (*KST_CHILDREN, *GEWST_CHILDREN):
			with self.subTest(doctype=name):
				listed = [field for field in definition(name)["fields"] if field.get("in_list_view")]
				self.assertLessEqual(sum(field.get("columns", 0) for field in listed), 10)

	def test_the_money_takes_the_currency_of_the_company(self):
		for name in ALL:
			for field in definition(name)["fields"]:
				if field["fieldtype"] == "Currency":
					with self.subTest(doctype=name, field=field["fieldname"]):
						self.assertEqual(field["options"], "Company:company:default_currency")


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


def messages_of_the_bridges() -> set[str]:
	"""What the bridges and the report give the Frappe layer to translate."""
	return {
		*bridge.MESSAGES,
		*bridge.LABELS.values(),
		*trade_bridge.MESSAGES,
		*trade_bridge.LABELS.values(),
		attribution.UNNUMBERED,
		*(str(kind) for kind in CarryForwardKind),
	}


class TranslationsFilesTest(TestCase):
	def test_the_sources_are_read(self):
		for text, found in (
			("Corporate Income Tax Return", texts_of_the_doctypes()),
			("Sale Price", texts_of_the_doctypes()),
			(bridge.NOT_REVIEWED_TEXT, messages_of_the_bridges()),
			(trade_bridge.NOT_CORRECTED, messages_of_the_bridges()),
		):
			with self.subTest(text=text):
				self.assertIn(text, found)

	def test_every_text_of_the_doctypes_is_translated(self):
		missing = texts_of_the_doctypes() - set(translations()) - FRAMEWORK_LABELS - UNTRANSLATED
		self.assertEqual(sorted(missing), [])

	def test_every_message_of_the_bridges_is_translated(self):
		self.assertEqual(sorted(messages_of_the_bridges() - set(translations()) - UNTRANSLATED), [])

	def test_the_framework_labels_are_left_to_the_framework(self):
		self.assertEqual(sorted(FRAMEWORK_LABELS & set(translations())), [])

	def test_the_translations_keep_the_placeholders(self):
		german = translations()
		for text in messages_of_the_bridges() - UNTRANSLATED:
			with self.subTest(text=text):
				self.assertCountEqual(PLACEHOLDER.findall(german[text]), PLACEHOLDER.findall(text))

	def test_the_returns_read_as_the_law_names_them(self):
		german = translations()
		self.assertEqual(german["Corporate Income Tax Return"], "Körperschaftsteuererklärung")
		self.assertEqual(german["Trade Tax Return"], "Gewerbesteuererklärung")
