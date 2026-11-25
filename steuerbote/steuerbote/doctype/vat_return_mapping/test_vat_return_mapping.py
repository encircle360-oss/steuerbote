from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.ustva import LATEST_YEAR, AccountRule, Mapping, Side, TaxCheck, WatchedAccount, WatchLevel

# The tests build their own companies and accounts and need none of ERPNext's test records.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Account"]

COMPANY = "Steuerbote Test Zuordnung GmbH"
OTHER_COMPANY = "Steuerbote Test Zuordnung Zwei GmbH"


def make_company(name: str, abbr: str) -> str:
	"""A company without a chart of accounts, so that it has only the accounts a test gives it."""
	if not frappe.db.exists("Company", name):
		flags = frappe.local.flags
		ignore_chart_of_accounts = flags.ignore_chart_of_accounts
		flags.ignore_chart_of_accounts = True
		try:
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": name,
					"abbr": abbr,
					"default_currency": "EUR",
					"country": "Germany",
				}
			).insert()
		finally:
			flags.ignore_chart_of_accounts = ignore_chart_of_accounts
	return name


def make_root(company: str, root_type: str) -> str:
	return make_account(company, None, root_type, None, is_group=True, root_type=root_type)


def make_account(
	company: str,
	number: str | None,
	name: str,
	parent: str | None,
	is_group: bool = False,
	root_type: str | None = None,
) -> str:
	if existing := frappe.db.get_value("Account", {"company": company, "account_name": name}):
		return existing
	account = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": name,
			"account_number": number,
			"company": company,
			"parent_account": parent,
			"is_group": int(is_group),
			"root_type": root_type,
		}
	)
	# A root account has no parent, which the DocType otherwise requires.
	return account.insert(ignore_mandatory=parent is None).name


class IntegrationTestVATReturnMapping(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STBZ")
		make_company(OTHER_COMPANY, "STBZ2")
		asset, liability, income, expense = (
			make_root(COMPANY, root_type) for root_type in ("Asset", "Liability", "Income", "Expense")
		)
		cls.input_tax_group = make_account(COMPANY, "1570", "Vorsteuer", asset, is_group=True)
		cls.accounts = {
			"8400": make_account(COMPANY, "8400", "Erlöse USt. 19 %", income),
			"8336": make_account(COMPANY, "8336", "Erlöse sonstige Leistungen EU", income),
			"1776": make_account(COMPANY, "1776", "Umsatzsteuer 19 %", liability),
			"1787": make_account(COMPANY, "1787", "Umsatzsteuer nach § 13b UStG 19 %", liability),
			"1576": make_account(COMPANY, "1576", "Abziehbare Vorsteuer 19 %", cls.input_tax_group),
			"3123": make_account(COMPANY, "3123", "Sonstige Leistungen EU 19 %", expense),
		}
		cls.bank = make_account(COMPANY, None, "Bank", asset)
		other_income = make_root(OTHER_COMPANY, "Income")
		cls.other_company_account = make_account(OTHER_COMPANY, "8300", "Erlöse USt. 7 %", other_income)
		# Watched by the defaults: 1548 at the blocking level, 8603 at the hint level.
		cls.other_watched = {
			"1548": make_account(
				OTHER_COMPANY, "1548", "Vorsteuer im Folgejahr abziehbar", make_root(OTHER_COMPANY, "Asset")
			),
			"8603": make_account(OTHER_COMPANY, "8603", "Sonstige betriebliche Erträge", other_income),
		}

	def new_mapping(self, chart="SKR03"):
		return frappe.get_doc({"doctype": "VAT Return Mapping", "company": COMPANY, "chart": chart})

	def insert(self, mapping):
		frappe.delete_doc_if_exists("VAT Return Mapping", COMPANY)
		return mapping.insert()

	def mapping_with_defaults(self):
		mapping = self.new_mapping()
		mapping.load_defaults()
		return mapping

	def test_load_defaults_keeps_the_rules_whose_account_exists(self):
		mapping = self.new_mapping()
		mapping.append("rules", {"account": self.accounts["8400"], "kennzahl": "86", "side": "credit"})
		mapping.load_defaults()
		self.assertEqual(
			[(row.account, row.account_number, row.kennzahl, row.side) for row in mapping.rules],
			[
				(self.accounts["8400"], "8400", "81", "credit"),
				(self.accounts["8336"], "8336", "21", "credit"),
				(self.accounts["3123"], "3123", "46", "debit"),
				(self.accounts["1576"], "1576", "66", "debit"),
			],
		)
		self.assertEqual(mapping.rules[2].tax_rate, 19)
		self.assertEqual(mapping.watched, [])

	def test_load_defaults_reduces_the_checks_to_the_accounts_that_exist(self):
		self.assertEqual(
			[
				(
					row.label,
					row.base_accounts,
					row.tax_accounts,
					row.side,
					row.derived_base or None,
					row.derived_base_eu or None,
				)
				for row in self.mapping_with_defaults().checks
			],
			[
				("Umsatzsteuer 19 %", "8400", "1776", "credit", "81", None),
				("Umsatzsteuer nach § 13b UStG 19 %", "3123", "1787", "credit", "84", "46"),
			],
		)

	def test_load_defaults_returns_the_default_accounts_the_company_lacks(self):
		missing = self.new_mapping().load_defaults()
		self.assertEqual(missing, sorted(missing))
		self.assertIn("8401", missing)
		self.assertIn("1570", missing, "a group account takes no postings")
		self.assertIn("8300", missing, "the account belongs to another company")
		self.assertNotIn("8400", missing)

	def test_load_defaults_needs_a_chart_with_defaults(self):
		with self.assertRaisesRegex(frappe.ValidationError, "There are no defaults for Eigener Kontenrahmen"):
			self.new_mapping("Eigener Kontenrahmen").load_defaults()

	def test_saved_defaults_give_the_core_mapping(self):
		self.insert(self.mapping_with_defaults())
		mapping = frappe.get_doc("VAT Return Mapping", COMPANY)
		self.assertEqual(
			mapping.to_mapping(LATEST_YEAR),
			Mapping(
				"SKR03",
				(
					AccountRule("8400", "81", Side.CREDIT),
					AccountRule("8336", "21", Side.CREDIT),
					AccountRule("3123", "46", Side.DEBIT, Decimal("19")),
					AccountRule("1576", "66", Side.DEBIT),
				),
				(
					TaxCheck("Umsatzsteuer 19 %", ("8400",), ("1776",), derived_base="81"),
					TaxCheck(
						"Umsatzsteuer nach § 13b UStG 19 %",
						("3123",),
						("1787",),
						derived_base="84",
						derived_base_eu="46",
					),
				),
				(),
				LATEST_YEAR,
			),
		)

	def test_a_kennzahl_that_takes_no_derived_base_is_refused(self):
		mapping = self.mapping_with_defaults()
		mapping.checks[0].derived_base = "84"
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"check 'Umsatzsteuer 19 %': base account 8400 feeds Kennzahl 81, which is no purchase",
		):
			self.insert(mapping)

	def test_the_account_number_is_fetched_from_the_account(self):
		mapping = self.new_mapping("Eigener Kontenrahmen")
		mapping.append("rules", {"account": self.accounts["8400"], "kennzahl": "81", "side": "credit"})
		mapping.append("watched", {"account": self.accounts["1776"]})
		self.insert(mapping)
		self.assertEqual(mapping.name, COMPANY)
		self.assertEqual(
			(mapping.rules[0].account_number, mapping.watched[0].account_number), ("8400", "1776")
		)
		self.assertEqual(mapping.to_mapping(LATEST_YEAR).watched, (WatchedAccount("1776"),))
		self.assertEqual(mapping.watched[0].level, "blocking")

	def test_a_watched_account_takes_its_level_into_the_core_mapping(self):
		mapping = self.new_mapping("Eigener Kontenrahmen")
		mapping.append("rules", {"account": self.accounts["8400"], "kennzahl": "81", "side": "credit"})
		mapping.append("watched", {"account": self.accounts["1776"], "level": "hint"})
		mapping.append("watched", {"account": self.accounts["8336"], "level": "blocking"})
		self.insert(mapping)
		self.assertEqual(
			frappe.get_doc("VAT Return Mapping", COMPANY).to_mapping(LATEST_YEAR).watched,
			(WatchedAccount("1776", WatchLevel.HINT), WatchedAccount("8336")),
		)

	def test_an_account_watched_twice_is_refused(self):
		mapping = self.new_mapping("Eigener Kontenrahmen")
		mapping.append("watched", {"account": self.accounts["1776"], "level": "hint"})
		mapping.append("watched", {"account": self.accounts["1776"]})
		with self.assertRaisesRegex(frappe.ValidationError, "account 1776 is watched twice"):
			self.insert(mapping)

	def test_load_defaults_gives_each_watched_account_the_level_of_the_defaults(self):
		mapping = frappe.get_doc(
			{"doctype": "VAT Return Mapping", "company": OTHER_COMPANY, "chart": "SKR03"}
		)
		mapping.load_defaults()
		self.assertEqual(
			[(row.account, row.account_number, row.level) for row in mapping.watched],
			[(self.other_watched["1548"], "1548", "blocking"), (self.other_watched["8603"], "8603", "hint")],
		)

	def test_load_defaults_keeps_the_level_a_watched_account_has(self):
		mapping = frappe.get_doc(
			{"doctype": "VAT Return Mapping", "company": OTHER_COMPANY, "chart": "SKR03"}
		)
		mapping.load_defaults()
		for row in mapping.watched:
			row.level = {"blocking": "hint", "hint": "blocking"}[row.level]
		mapping.load_defaults()
		self.assertEqual(
			[(row.account_number, row.level) for row in mapping.watched],
			[("1548", "hint"), ("8603", "blocking")],
		)
		frappe.delete_doc_if_exists("VAT Return Mapping", OTHER_COMPANY)
		mapping.insert()
		self.assertEqual(
			frappe.get_doc("VAT Return Mapping", OTHER_COMPANY).to_mapping(LATEST_YEAR).watched,
			(WatchedAccount("1548", WatchLevel.HINT), WatchedAccount("8603")),
		)

	def test_an_account_mapped_twice_is_refused(self):
		mapping = self.mapping_with_defaults()
		mapping.append("rules", {"account": self.accounts["8400"], "kennzahl": "86", "side": "credit"})
		with self.assertRaisesRegex(frappe.ValidationError, "account 8400 is mapped twice"):
			mapping.insert()

	def test_an_account_without_number_is_refused(self):
		mapping = self.new_mapping()
		mapping.append("rules", {"account": self.bank, "kennzahl": "81", "side": "credit"})
		with self.assertRaisesRegex(frappe.ValidationError, f"account {self.bank} has no account number"):
			mapping.insert()

	def test_an_account_of_another_company_is_refused(self):
		mapping = self.new_mapping()
		mapping.append("rules", {"account": self.other_company_account, "kennzahl": "86", "side": "credit"})
		with self.assertRaisesRegex(frappe.ValidationError, "does not belong to company"):
			mapping.insert()

	def test_a_group_account_is_refused(self):
		mapping = self.new_mapping()
		mapping.append("watched", {"account": self.input_tax_group})
		with self.assertRaisesRegex(frappe.ValidationError, "is a group"):
			mapping.insert()

	def test_a_year_without_catalogue_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "no Kennzahlen catalogue for 2019"):
			self.mapping_with_defaults().to_mapping(2019)
