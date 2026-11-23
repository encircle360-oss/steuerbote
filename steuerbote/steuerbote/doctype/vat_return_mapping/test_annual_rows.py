"""The rows of the VAT Return Mapping for the annual return on a site: Vorgaben laden with the accounts only the annual
return reads, the annual field and paragraph of a rule kept or dropped, what saving refuses, the line of each account
the annual return reads, Vorgaben aktualisieren for a mapping from before, and the file of a mapping."""

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.mapping_sync import annual_default_items, default_items, dump_items, load_items
from steuerbote.tests.helpers import make_account, make_company
from steuerbote.ustjahr.split import How
from steuerbote.ustjahr.years import LATEST_YEAR as ANNUAL_YEAR
from steuerbote.ustva import LATEST_YEAR

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

MAPPING = "VAT Return Mapping"
COMPANY = "Steuerbote Test Jahreszuordnung GmbH"
TARGET = "Steuerbote Test Jahreszuordnung Ziel GmbH"
OTHER = "Steuerbote Test Jahreszuordnung Fremd GmbH"
# SKR03 accounts: a sale at 19 % with its tax, an Entnahme, a correction under § 15a UStG, the sale and the purchase of
# the first buyer of a Dreiecksgeschäft, a purchase from a Umsatzsteuerlager with the tax of its Auslagerung, and a
# bank, which the defaults leave out.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"8910": ("Entnahme durch den Unternehmer (Waren) 19 % USt", "Income"),
	"1558": ("Nachträglich abziehbare Vorsteuer nach § 15a Abs. 1 UStG, unbewegliche WG", "Asset"),
	"8130": ("Lieferungen des ersten Abnehmers bei innergemeinschaftlichen Dreiecksgeschäften", "Income"),
	"3552": ("Erwerb 1. Abnehmer innerhalb eines Dreiecksgeschäftes", "Expense"),
	"3075": ("Einkauf Roh-, Hilfs- und Betriebsstoffe aus einem USt-Lager 7 %", "Expense"),
	"1769": ("Umsatzsteuer aus der Auslagerung von Gegenständen aus einem Umsatzsteuerlager", "Liability"),
	"1200": ("Bank", "Asset"),
}


def make_accounts(company: str) -> dict[str, str]:
	return {
		number: frappe.db.get_value("Account", {"company": company, "account_number": number})
		or make_account(company, number, name, root_type)
		for number, (name, root_type) in ACCOUNTS.items()
	}


def new_mapping(company: str, chart: str = "SKR03"):
	frappe.delete_doc_if_exists(MAPPING, company, force=True)
	mapping = frappe.new_doc(MAPPING)
	mapping.update({"company": company, "chart": chart})
	if chart != "Eigener Kontenrahmen":
		mapping.load_defaults()
	return mapping.insert()


def annual_rows(mapping) -> list[tuple]:
	return [
		(row.account, row.account_number, row.annual_field, row.side, row.paragraph or None)
		for row in mapping.annual_rules
	]


def rule_of(mapping, number: str):
	return next(row for row in mapping.rules if row.account_number == number)


def ids(comparison: dict) -> list[tuple[str, bool]]:
	return [(difference["id"], difference["proposes"]) for difference in comparison["differences"]]


class IntegrationTestAnnualRows(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STJZ")
		make_company(TARGET, "STJT")
		make_company(OTHER, "STJF")
		cls.accounts = make_accounts(COMPANY)
		cls.target_accounts = make_accounts(TARGET)
		cls.other_account = frappe.db.get_value(
			"Account", {"company": OTHER, "account_number": "3552"}
		) or make_account(OTHER, "3552", ACCOUNTS["3552"][0], "Expense")

	def setUp(self):
		new_mapping(COMPANY)

	def test_vorgaben_laden_reads_the_accounts_only_the_annual_return_reads(self):
		mapping = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(
			annual_rows(mapping),
			[
				(self.accounts["3552"], "3552", "E3100801", "debit", None),
				(self.accounts["3075"], "3075", "E3102804", "debit", None),
			],
		)
		self.assertEqual({row.account_number for row in mapping.watched}, {"3075", "1769"})
		self.assertEqual(
			{(row.annual_field or None, row.paragraph or None) for row in mapping.rules}, {(None, None)}
		)

	def test_the_stored_defaults_hold_the_rows_for_the_annual_return(self):
		mapping = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(
			load_items(mapping.defaults_rows),
			{
				**default_items("SKR03", LATEST_YEAR, set(ACCOUNTS)),
				**annual_default_items("SKR03", ANNUAL_YEAR, set(ACCOUNTS)),
			},
		)
		self.assertEqual(mapping.compare_with_defaults()["differences"], [])

	def test_vorgaben_laden_keeps_the_annual_field_of_a_rule_whose_kennzahl_stays(self):
		mapping = frappe.get_doc(MAPPING, COMPANY)
		rule_of(mapping, "8910").annual_field = "E3003505"
		sale = rule_of(mapping, "8400")
		sale.kennzahl, sale.annual_field = "86", "E3003703"
		mapping.load_defaults()
		self.assertEqual(
			(rule_of(mapping, "8910").kennzahl, rule_of(mapping, "8910").annual_field), ("81", "E3003505")
		)
		self.assertEqual(
			(rule_of(mapping, "8400").kennzahl, rule_of(mapping, "8400").annual_field or None), ("81", None)
		)
		mapping.save()
		self.assertEqual(ids(mapping.compare_with_defaults()), [("annual_field:8910", False)])

	def test_saving_refuses_an_annual_field_the_kennzahl_of_the_rule_does_not_take(self):
		mapping = frappe.get_doc(MAPPING, COMPANY)
		rule_of(mapping, "8910").annual_field = "E3003703"
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"Account 8910 feeds Kennzahl 81 of the Voranmeldung, which field E3003703 in line 28 does not take",
		):
			mapping.save()
		frappe.clear_messages()

	def test_saving_refuses_a_row_for_the_annual_return_only_on_a_mapped_account(self):
		mapping = frappe.get_doc(MAPPING, COMPANY)
		mapping.append(
			"annual_rules", {"account": self.accounts["8400"], "annual_field": "E3100801", "side": "debit"}
		)
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"Account 8400 feeds Kennzahl 81 of the Voranmeldung, so its line comes from",
		):
			mapping.save()
		frappe.clear_messages()

	def test_saving_refuses_an_account_of_another_company_for_the_annual_return(self):
		mapping = frappe.get_doc(MAPPING, COMPANY)
		mapping.append(
			"annual_rules", {"account": self.other_account, "annual_field": "E3100801", "side": "debit"}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "does not belong to company"):
			mapping.save()
		frappe.clear_messages()

	def test_a_line_only_the_annual_return_asks_for_does_not_hold_the_mapping(self):
		"""A chart of its own has no roles, and Kz 64 has no default line: saving works, the split names the gap."""
		mapping = new_mapping(COMPANY, "Eigener Kontenrahmen")
		mapping.append("rules", {"account": self.accounts["1558"], "kennzahl": "64", "side": "debit"})
		mapping.save()
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"Account 1558 feeds Kennzahl 64 of the Voranmeldung, which splits into lines",
		):
			mapping.to_split(ANNUAL_YEAR)
		frappe.clear_messages()
		rule_of(mapping, "1558").annual_field = "E3008701"
		mapping.save()
		self.assertEqual(mapping.to_split(ANNUAL_YEAR).field_of("1558"), "E3008701")

	def test_the_annual_return_reads_the_line_of_each_account(self):
		mapping = frappe.get_doc(MAPPING, COMPANY)
		rule_of(mapping, "8400").annual_field = "E3003303"
		mapping.save()
		result = mapping.to_split(ANNUAL_YEAR)
		self.assertEqual(
			{number: (assignment.field, assignment.how) for number, assignment in result.assignments.items()},
			{
				"8400": ("E3003303", How.RULE),
				"8910": ("E3003405", How.ROLE),
				"1558": ("E3008701", How.ROLE),
				"8130": ("E3101801", How.DEFAULT),
				"3552": ("E3100801", How.ANNUAL),
				"3075": ("E3102804", How.ANNUAL),
			},
		)
		self.assertEqual(result.mapping.year, ANNUAL_YEAR)

	def test_vorgaben_aktualisieren_proposes_the_rows_for_the_annual_return_to_a_mapping_from_before(self):
		"""A mapping that took over the defaults before Steuerbote knew the rows for the annual return."""
		mapping = frappe.get_doc(MAPPING, COMPANY)
		before = default_items("SKR03", LATEST_YEAR, set(ACCOUNTS))
		mapping._set_items(before)
		mapping.defaults_rows = dump_items(before)
		mapping.save()
		comparison = mapping.compare_with_defaults()
		self.assertEqual(
			[
				(difference["id"], difference["proposes"], difference["subject"], difference["change"])
				for difference in comparison["differences"]
			],
			[
				("annual_rule:3552", True, "Account 3552 for the Annual Return Only", "Will Be Added"),
				("annual_rule:3075", True, "Account 3075 for the Annual Return Only", "Will Be Added"),
			],
		)
		self.assertEqual(comparison["differences"][0]["proposed"], "Field E3100801, debit")
		self.assertEqual(mapping.update_from_defaults(["annual_rule:3552", "annual_rule:3075"]), 2)
		self.assertEqual(
			annual_rows(frappe.get_doc(MAPPING, COMPANY)),
			[
				(self.accounts["3552"], "3552", "E3100801", "debit", None),
				(self.accounts["3075"], "3075", "E3102804", "debit", None),
			],
		)

	def test_the_file_of_a_mapping_carries_its_annual_fields_and_rows_for_the_annual_return(self):
		source = frappe.get_doc(MAPPING, COMPANY)
		rule_of(source, "8910").annual_field = "E3003505"
		source.save()
		text = source.export_mapping()["content"]
		target = new_mapping(TARGET)
		comparison = target.compare_with_file(content=text)
		self.assertEqual(ids(comparison), [("annual_field:8910", True)])
		self.assertEqual(comparison["differences"][0]["subject"], "Annual Return Field of Account 8910")
		self.assertEqual(target.import_file(content=text, chosen=["annual_field:8910"]), 1)
		imported = frappe.get_doc(MAPPING, TARGET)
		self.assertEqual(rule_of(imported, "8910").annual_field, "E3003505")
		self.assertEqual(
			[row[1:] for row in annual_rows(imported)],
			[row[1:] for row in annual_rows(frappe.get_doc(MAPPING, COMPANY))],
		)
		self.assertEqual(
			load_items(imported.defaults_rows), load_items(frappe.get_doc(MAPPING, COMPANY).defaults_rows)
		)
