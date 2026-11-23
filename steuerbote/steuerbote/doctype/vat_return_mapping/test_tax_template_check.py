"""Steuervorlagen prüfen: the accounts of a company's tax templates without a place in its VAT Return Mapping, at the
mapping and as hints of Berechnen."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import fmt_money

from steuerbote.tax_templates import template_accounts
from steuerbote.tests.helpers import (
	insert_record,
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

# The companies, their accounts and templates are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

COMPANY = "Steuerbote Test Steuervorlagen GmbH"
ABBR = "STSV"
OTHER_COMPANY = "Steuerbote Test Steuervorlagen Zwei GmbH"
OTHER_ABBR = "STSW"

# SKR03 numbers: 1776 is checked, 1576 mapped, 1548 watched and 1767 (OSS) deliberately without Kennzahl by the
# defaults; 1775 and 1773 have no place there.
ACCOUNTS = {
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1775": ("Umsatzsteuer 16 %", "Liability"),
	"1773": ("Umsatzsteuer Altfall", "Liability"),
	"1767": ("Umsatzsteuer aus im anderen EU-Land steuerpflichtigen Lieferungen", "Liability"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1548": ("Vorsteuer im Folgejahr abziehbar", "Asset"),
	"1200": ("Bank", "Asset"),
}
WITHOUT_NUMBER = "Steuer Sonderfall"
CHECK = "STEUERVORLAGE-OHNE-KENNZAHL"


def euros(amount: int) -> str:
	return fmt_money(amount, currency="EUR")


def make_template(
	company: str, abbr: str, doctype: str, title: str, accounts: list[str], disabled: int = 0
) -> str:
	"""A tax template with a row per account, as ERPNext keeps it."""
	name = f"{title} - {abbr}"
	insert_record(doctype, name=name, title=title, company=company, disabled=disabled)
	table, field = {
		"Sales Taxes and Charges Template": ("Sales Taxes and Charges", "account_head"),
		"Purchase Taxes and Charges Template": ("Purchase Taxes and Charges", "account_head"),
		"Item Tax Template": ("Item Tax Template Detail", "tax_type"),
	}[doctype]
	for idx, account in enumerate(accounts, start=1):
		insert_record(
			table,
			name=f"{name}-{idx}",
			parent=name,
			parenttype=doctype,
			parentfield="taxes",
			idx=idx,
			description=title,
			**{field: account},
		)
	return name


class TestTaxTemplateCheck(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, ABBR)
		a = cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		cls.without_number = make_account(COMPANY, None, WITHOUT_NUMBER, "Liability")
		make_settings(COMPANY, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
		sales, purchases, items = (
			"Sales Taxes and Charges Template",
			"Purchase Taxes and Charges Template",
			"Item Tax Template",
		)
		cls.templates = {
			"19": make_template(COMPANY, ABBR, sales, "Inland 19 %", [a["1776"]]),
			"16": make_template(COMPANY, ABBR, sales, "Inland 16 %", [a["1775"], a["1776"]]),
			"oss": make_template(COMPANY, ABBR, sales, "OSS Österreich", [a["1767"]]),
			"purchases": make_template(COMPANY, ABBR, purchases, "Einkauf Inland", [a["1576"], a["1548"]]),
			"items": make_template(COMPANY, ABBR, items, "Artikel 16 %", [a["1775"], cls.without_number]),
		}
		make_template(COMPANY, ABBR, sales, "Altfall", [a["1773"]], disabled=1)
		make_company(OTHER_COMPANY, OTHER_ABBR)
		other = make_account(OTHER_COMPANY, "1775", "Umsatzsteuer 16 %", "Liability")
		make_template(OTHER_COMPANY, OTHER_ABBR, sales, "Inland 16 %", [other])
		post_journal_entry(COMPANY, "2026-10-12", [(a["1200"], 16, 0), (a["1775"], 0, 16)])

	def roll_back_afterwards(self) -> None:
		frappe.db.savepoint("tax_template_test")
		self.addCleanup(frappe.db.rollback, save_point="tax_template_test")

	def calculated(self, period: int):
		doc = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": period,
			}
		).insert()
		doc.calculate()
		doc.reload()
		return doc

	def test_reads_every_account_of_the_enabled_templates_of_the_company(self):
		t = self.templates
		self.assertEqual(
			[
				(account.account, account.account_number, account.account_name, account.templates)
				for account in template_accounts(COMPANY)
			],
			[
				(self.account["1548"], "1548", ACCOUNTS["1548"][0], (t["purchases"],)),
				(self.account["1576"], "1576", ACCOUNTS["1576"][0], (t["purchases"],)),
				(self.account["1767"], "1767", ACCOUNTS["1767"][0], (t["oss"],)),
				(self.account["1775"], "1775", ACCOUNTS["1775"][0], (t["16"], t["items"])),
				(self.account["1776"], "1776", ACCOUNTS["1776"][0], (t["16"], t["19"])),
				(self.without_number, None, WITHOUT_NUMBER, (t["items"],)),
			],
		)

	def test_the_check_names_the_accounts_without_a_place_in_the_mapping(self):
		mapping = frappe.get_doc("VAT Return Mapping", COMPANY)
		self.assertEqual(
			mapping.check_tax_templates(),
			[
				{
					"account": self.account["1775"],
					"account_number": "1775",
					"account_name": ACCOUNTS["1775"][0],
					"templates": [self.templates["16"], self.templates["items"]],
				},
				{
					"account": self.without_number,
					"account_number": "",
					"account_name": WITHOUT_NUMBER,
					"templates": [self.templates["items"]],
				},
			],
		)

	def test_the_check_reads_the_mapping_as_the_form_holds_it(self):
		mapping = frappe.get_doc("VAT Return Mapping", COMPANY)
		mapping.append(
			"watched", {"account": self.account["1775"], "account_number": "1775", "level": "hint"}
		)
		self.assertEqual([row["account_number"] for row in mapping.check_tax_templates()], [""])

	def test_watching_adds_the_accounts_with_a_number_at_the_level_blocking_and_saves(self):
		self.roll_back_afterwards()
		mapping = frappe.get_doc("VAT Return Mapping", COMPANY)
		self.assertEqual(mapping.watch_template_accounts(), [self.account["1775"]])
		saved = frappe.get_doc("VAT Return Mapping", COMPANY)
		self.assertIn(
			(self.account["1775"], "1775", "blocking"),
			[(r.account, r.account_number, r.level) for r in saved.watched],
		)
		self.assertEqual([row["account"] for row in saved.check_tax_templates()], [self.without_number])
		with self.assertRaisesRegex(frappe.ValidationError, "mit Kontonummer|with an account number"):
			saved.watch_template_accounts()

	def test_berechnen_gives_a_hint_per_account_without_place_and_holds_nothing(self):
		doc = self.calculated(10)
		self.assertEqual((doc.ready, doc.status), (1, "Bereit"))
		with_balance = (
			f"Konto 1775 Umsatzsteuer 16 % aus den Steuervorlagen „{self.templates['16']}“ und "
			f"„{self.templates['items']}“ hat keinen Platz in der Kontenzuordnung und im Zeitraum einen "
			f"Saldo von {euros(16)} im Haben (Soll {euros(0)}, Haben {euros(16)}), der in keine Kennzahl "
			"eingeht."
		)
		without_number = (
			f"Konto {WITHOUT_NUMBER} aus der Steuervorlage „{self.templates['items']}“ hat keine "
			"Kontonummer, deshalb kann keine Regel der Kontenzuordnung es zuordnen."
		)
		self.assertEqual(
			[(row.severity, row.text) for row in doc.hints if row.code == CHECK],
			[("Hinweis", with_balance), ("Hinweis", without_number)],
		)

	def test_a_month_without_postings_names_the_account_without_a_balance(self):
		doc = self.calculated(9)
		self.assertIn(
			"hat keinen Platz in der Kontenzuordnung; im Zeitraum hat es keinen Saldo.",
			next(row.text for row in doc.hints if row.code == CHECK),
		)

	def test_an_account_watched_after_the_check_holds_the_return_instead(self):
		self.roll_back_afterwards()
		frappe.get_doc("VAT Return Mapping", COMPANY).watch_template_accounts()
		doc = self.calculated(10)
		self.assertEqual((doc.ready, doc.status), (0, "Berechnet"))
		self.assertEqual([row.account_number for row in doc.unmapped], ["1775"])
		self.assertEqual([row.code for row in doc.hints if row.code == CHECK], [CHECK])
