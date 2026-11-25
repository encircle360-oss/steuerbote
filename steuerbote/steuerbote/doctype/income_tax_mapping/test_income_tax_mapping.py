"""The Income Tax Mapping on a site: Vorgaben laden for the accounts a company has, with the DATEV accounts it lacks,
and the checks of saving."""

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.income_tax_mapping_sync import default_items, load_items
from steuerbote.kst.categories import Category, TradingClass
from steuerbote.kst.defaults import default_accounts
from steuerbote.tests.helpers import make_account, make_company

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

MAPPING = "Income Tax Mapping"
COMPANY = "Steuerbote Test Ertragsteuern GmbH"
OTHER_COMPANY = "Steuerbote Test Ertragsteuern Andere GmbH"
# SKR03 accounts: the taxes on income, a trading account, a watched account at each level, a bank and the
# Gezeichnetes Kapital, which the defaults leave out.
ACCOUNTS = {
	"2200": ("Körperschaftsteuer", "Expense"),
	"2208": ("Solidaritätszuschlag", "Expense"),
	"4320": ("Gewerbesteuer", "Expense"),
	"2654": ("Erträge aus anderen Wertpapieren und Ausleihungen des Umlaufvermögens", "Income"),
	"2250": ("Aufwendungen aus der Zuführung und Auflösung von latenten Steuern", "Expense"),
	"4126": ("Tantiemen Gesellschafter-Geschäftsführer", "Expense"),
	"1200": ("Bank", "Asset"),
	"0800": ("Gezeichnetes Kapital", "Equity"),
}


def make_accounts(company: str) -> dict[str, str]:
	return {
		number: frappe.db.get_value("Account", {"company": company, "account_number": number})
		or make_account(company, number, name, root_type)
		for number, (name, root_type) in ACCOUNTS.items()
	}


class IntegrationTestIncomeTaxMapping(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STET")
		make_company(OTHER_COMPANY, "STETA")
		cls.accounts = make_accounts(COMPANY)
		cls.other_accounts = make_accounts(OTHER_COMPANY)

	def setUp(self):
		frappe.delete_doc_if_exists(MAPPING, COMPANY, force=True)
		self.mapping = frappe.new_doc(MAPPING)
		self.mapping.update({"company": COMPANY, "chart": "SKR03"})

	def test_vorgaben_laden_takes_the_defaults_of_the_accounts_the_company_has(self):
		missing = self.mapping.load_defaults()
		self.assertEqual(
			[
				(row.account, row.account_number, row.category, row.trading_class)
				for row in self.mapping.rules
			],
			[
				(self.accounts["2200"], "2200", "kst", None),
				(self.accounts["2208"], "2208", "solz", None),
				(self.accounts["4320"], "4320", "gewst", None),
				(self.accounts["2654"], "2654", "trading_unclassified", None),
			],
		)
		self.assertEqual(
			[(row.account, row.account_number, row.level) for row in self.mapping.watched],
			[(self.accounts["2250"], "2250", "blocking"), (self.accounts["4126"], "4126", "hint")],
		)
		self.assertEqual(len(missing), len(default_accounts("SKR03")) - 6)
		self.assertEqual(
			missing[0], {"account_number": "2004", "label": "Verluste durch Verschmelzung und Umwandlung"}
		)
		self.assertIn({"account_number": "2203", "label": "Körperschaftsteuer für Vorjahre"}, missing)
		self.mapping.insert()
		stored = frappe.get_doc(MAPPING, COMPANY)
		self.assertEqual(stored.defaults_version, "SKR03 2026.2")
		self.assertEqual(load_items(stored.defaults_rows), default_items("SKR03", set(ACCOUNTS)))
		self.assertEqual(stored.current_items(), default_items("SKR03", set(ACCOUNTS)))

	def test_vorgaben_laden_keeps_the_level_of_a_watched_account(self):
		self.mapping.load_defaults()
		self.mapping.insert()
		for row in self.mapping.watched:
			row.level = "hint"
		self.mapping.load_defaults()
		self.mapping.save()
		self.assertEqual(
			[(row.account_number, row.level) for row in self.mapping.watched],
			[("2250", "hint"), ("4126", "hint")],
		)

	def test_the_core_reads_the_rules_with_the_class_of_a_trading_account(self):
		self.mapping.load_defaults()
		(trading,) = (row for row in self.mapping.rules if row.account_number == "2654")
		trading.trading_class = "derivatives"
		self.mapping.insert()
		core = frappe.get_doc(MAPPING, COMPANY).to_mapping()
		self.assertEqual(core.chart, "SKR03")
		self.assertEqual(
			(core.rule_for("2654").category, core.rule_for("2654").trading_class),
			(Category.TRADING_UNCLASSIFIED, TradingClass.DERIVATIVES),
		)
		self.assertEqual(core.rule_for("2200").category, Category.KST)

	def test_a_trading_class_on_another_category_is_refused(self):
		self.mapping.append(
			"rules", {"account": self.accounts["2200"], "category": "kst", "trading_class": "shares"}
		)
		with self.assertRaisesRegex(
			frappe.ValidationError, "account 2200: a trading class needs the category trading_unclassified"
		):
			self.mapping.insert()

	def test_a_refused_row_shows_what_it_holds_as_text(self):
		self.mapping.append("rules", {"account": self.accounts["2200"], "category": "<b>kst</b>"})
		with self.assertRaisesRegex(frappe.ValidationError, "not &apos;&lt;b&gt;kst&lt;/b&gt;&apos;"):
			self.mapping.insert()

	def test_an_account_has_one_place(self):
		self.mapping.append("rules", {"account": self.accounts["2200"], "category": "kst"})
		self.mapping.append("watched", {"account": self.accounts["2200"], "level": "hint"})
		with self.assertRaisesRegex(frappe.ValidationError, "account 2200 is mapped and watched"):
			self.mapping.insert()

	def test_an_account_of_another_company_or_a_group_is_refused(self):
		self.mapping.append("rules", {"account": self.other_accounts["2200"], "category": "kst"})
		with self.assertRaisesRegex(frappe.ValidationError, "does not belong to company"):
			self.mapping.insert()
		frappe.clear_messages()
		group = frappe.db.get_value("Account", {"company": COMPANY, "is_group": 1, "root_type": "Expense"})
		self.mapping.set("rules", [])
		self.mapping.append("watched", {"account": group, "level": "blocking"})
		with self.assertRaisesRegex(frappe.ValidationError, "is a group and takes no postings"):
			self.mapping.insert()

	def test_a_chart_of_its_own_and_a_mapping_without_company_have_no_defaults(self):
		self.mapping.chart = "Eigener Kontenrahmen"
		with self.assertRaisesRegex(frappe.ValidationError, "There are no defaults for Eigener Kontenrahmen"):
			self.mapping.load_defaults()
		frappe.clear_messages()
		self.mapping.update({"company": None, "chart": "SKR03"})
		with self.assertRaisesRegex(frappe.ValidationError, "Select the company first"):
			self.mapping.load_defaults()
