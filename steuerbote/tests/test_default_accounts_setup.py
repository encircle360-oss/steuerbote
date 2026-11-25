"""The step „Standardkonten des Unternehmens“ of Steuerbote einrichten on a site: it names a default account of the
company for discounts, write-offs or roundings that would hold a return, and changes nothing. Every name and number is
invented."""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.setup.chart import Basis, Detection
from steuerbote.setup.steps import Outcome
from steuerbote.steuerbote import default_accounts_setup
from steuerbote.tests.helpers import make_account, make_company

COMPANY = "Steuerbote Test Standardkonten GmbH"
SKR03 = SimpleNamespace(
	company=COMPANY, chart=Detection("SKR03", Basis.ACCOUNTS), today=frappe.utils.getdate("2026-11-25")
)


class TestDefaultAccountsSetup(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STSK")
		cls.discount = make_account(COMPANY, "8730", "Gewährte Skonti", "Income")
		cls.discount_19 = make_account(COMPANY, "8736", "Gewährte Skonti 19 % USt", "Income")
		cls.write_off = make_account(COMPANY, "2400", "Forderungsverluste", "Expense")
		cls.round_off = make_account(COMPANY, "2309", "Sonstige Aufwendungen unregelmäßig", "Expense")
		cls.own = make_account(COMPANY, "2318", "Rundungsdifferenzen", "Expense")

	def setUp(self):
		frappe.db.savepoint("default_accounts_setup_test")
		self.addCleanup(frappe.db.rollback, save_point="default_accounts_setup_test")
		frappe.db.set_value("Company", COMPANY, dict.fromkeys(default_accounts_setup.FIELDS))

	def test_names_each_default_account_that_would_hold_a_return_and_changes_nothing(self):
		frappe.db.set_value(
			"Company",
			COMPANY,
			{
				"default_discount_account": self.discount,
				"write_off_account": self.write_off,
				"round_off_account": self.own,
			},
		)
		result = default_accounts_setup.check(SKR03)
		self.assertEqual((result.outcome, result.action), (Outcome.UNDECIDED, None))
		self.assertEqual(
			[(note.template, note.values[2]) for note in result.notes],
			[
				(default_accounts_setup.HOLDS_VAT, "8730"),
				(default_accounts_setup.HOLDS_VAT, "2400"),
				(default_accounts_setup.UNKNOWN, "2318"),
			],
		)
		self.assertEqual(result.notes[0].values[3], "8736 (19 %), 8731 (7 %), 8734 (0 %)")
		self.assertEqual(frappe.db.get_value("Company", COMPANY, "default_discount_account"), self.discount)

	def test_accounts_that_hold_nothing_back_leave_the_step_done(self):
		frappe.db.set_value(
			"Company",
			COMPANY,
			{"default_discount_account": self.discount_19, "round_off_account": self.round_off},
		)
		result = default_accounts_setup.check(SKR03)
		self.assertEqual(result.outcome, Outcome.SKIPPED)
		self.assertEqual([note.template for note in result.notes], [default_accounts_setup.FINE])

	def test_a_row_of_the_company_for_the_account_ends_the_note_on_the_voranmeldung(self):
		frappe.db.set_value("Company", COMPANY, "default_discount_account", self.discount)
		with self.subTest("without a mapping the defaults of the chart count"):
			self.assertEqual(default_accounts_setup.check(SKR03).outcome, Outcome.UNDECIDED)
		mapped = default_accounts_setup.blocking_accounts(COMPANY, "SKR03", 2026) - {"8730"}
		with patch.object(default_accounts_setup, "blocking_accounts", return_value=mapped):
			self.assertEqual(default_accounts_setup.check(SKR03).outcome, Outcome.SKIPPED)

	def test_a_chart_of_its_own_has_nothing_to_compare_with(self):
		frappe.db.set_value("Company", COMPANY, "default_discount_account", self.discount)
		result = default_accounts_setup.check(
			SimpleNamespace(company=COMPANY, chart=Detection(None, Basis.NONE), today=SKR03.today)
		)
		self.assertEqual(result.outcome, Outcome.SKIPPED)
