"""The step „Konten der Wechselkursdifferenzen“ of Steuerbote einrichten on a site: it proposes the accounts of the
currency translation of the chart for ERPNext's two exchange accounts of the company, changes nothing while it only
shows the status, and sets the empty ones by its action. Every name and number is invented."""

from types import SimpleNamespace

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.setup.chart import Basis, Detection
from steuerbote.setup.steps import Outcome
from steuerbote.steuerbote import exchange_setup
from steuerbote.tests.helpers import make_account, make_company

COMPANY = "Steuerbote Test Wechselkurs GmbH"
BARE = "Steuerbote Test Wechselkurs ohne Konten GmbH"
SKR03 = SimpleNamespace(company=COMPANY, chart=Detection("SKR03", Basis.ACCOUNTS))


def accounts(company: str) -> tuple:
	return tuple(frappe.db.get_value("Company", company, list(exchange_setup.FIELDS)))


class TestExchangeSetup(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STWK")
		make_company(BARE, "STWO")
		cls.realised = make_account(
			COMPANY, "2151", "Aufwendungen aus der Währungsumrechnung (nicht § 256a HGB)", "Expense"
		)
		cls.revalued = make_account(COMPANY, "2150", "Aufwendungen aus der Währungsumrechnung", "Expense")

	def setUp(self):
		frappe.db.savepoint("exchange_setup_test")
		self.addCleanup(frappe.db.rollback, save_point="exchange_setup_test")
		for company in (COMPANY, BARE):
			frappe.db.set_value("Company", company, dict.fromkeys(exchange_setup.FIELDS))

	def test_proposes_the_accounts_of_the_chart_and_changes_nothing_by_itself(self):
		result = exchange_setup.check(SKR03)
		self.assertEqual(
			(result.outcome, result.action.method),
			(Outcome.UNDECIDED, f"{exchange_setup.__name__}.set_exchange_accounts"),
		)
		(note,) = result.notes
		self.assertEqual(note.template, exchange_setup.PROPOSED)
		self.assertEqual(note.values, (COMPANY, "2151", "2150"))
		self.assertEqual(accounts(COMPANY), (None, None))

	def test_the_action_sets_the_empty_accounts_and_the_step_is_done(self):
		exchange_setup.set_exchange_accounts(COMPANY)
		self.assertEqual(accounts(COMPANY), (self.realised, self.revalued))
		self.assertEqual(exchange_setup.check(SKR03).outcome, Outcome.SKIPPED)

	def test_an_account_chosen_by_the_company_stays(self):
		frappe.db.set_value("Company", COMPANY, "exchange_gain_loss_account", self.revalued)
		exchange_setup.set_exchange_accounts(COMPANY)
		self.assertEqual(accounts(COMPANY), (self.revalued, self.revalued))

	def test_without_the_accounts_or_without_a_chart_it_says_what_to_do(self):
		missing = exchange_setup.check(
			SimpleNamespace(company=BARE, chart=Detection("SKR04", Basis.ACCOUNTS))
		)
		self.assertEqual((missing.outcome, missing.action), (Outcome.UNDECIDED, None))
		self.assertEqual(missing.notes[0].template, exchange_setup.MISSING)
		self.assertEqual(missing.notes[0].values, (BARE, "6881, 6880"))
		own = exchange_setup.check(SimpleNamespace(company=BARE, chart=Detection(None, Basis.NONE)))
		self.assertEqual((own.outcome, own.notes[0].template), (Outcome.UNDECIDED, exchange_setup.OWN_CHART))
