"""The first year of a company in Steuerbote, on a site: it kept its books with a tax adviser until the end of 2025 and
starts in ERPNext on 1 January 2026 with opening entries only (steuerbote/setup/start.py). Nothing of 2025 is in the
ledger; what later filings need of it comes from the Voranmeldungen filed before Steuerbote. The company, its accounts
and every amount are invented."""

from datetime import date
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import balances, income_tax_sources, prior_filings
from steuerbote.setup import start
from steuerbote.setup.steps import Outcome
from steuerbote.steuerbote import deadlines, setup
from steuerbote.tests.helpers import (
	ensure_fiscal_year,
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "VAT Return"]

# Starts on 1 January 2026 and names the start in its settings; files the Voranmeldung and the ZM monthly.
COMPANY = "Steuerbote Test Erstes Jahr GmbH"
# Starts the same way, but has not set up Steuerbote yet.
NEW_COMPANY = "Steuerbote Test Erstes Jahr Einrichtung GmbH"
# Posted its opening balances on 31 December 2025 and names no start.
DECEMBER_COMPANY = "Steuerbote Test Eröffnung im Dezember GmbH"
BOOKS_START = date(2026, 1, 1)
ACCOUNTS = {
	"1548": ("Vorsteuer in Folgeperiode/im Folgejahr abziehbar", "Asset"),
	"1576": ("Abziehbare Vorsteuer 19 %", "Asset"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1790": ("Umsatzsteuer Vorjahr", "Liability"),
	"1200": ("Bank", "Asset"),
	"0800": ("Gezeichnetes Kapital", "Equity"),
	"8400": ("Erlöse 19 % USt", "Income"),
}


def accounts_of(company: str) -> dict[str, str]:
	return {
		number: frappe.db.get_value("Account", {"company": company, "account_number": number})
		or make_account(company, number, name, root_type)
		for number, (name, root_type) in ACCOUNTS.items()
	}


def open_books(company: str, accounts: dict[str, str], day: str) -> None:
	"""The opening entry: the bank, the prior-year VAT liability, and 1.900 € of Vorsteuer deductible in January."""
	post_journal_entry(
		company,
		day,
		[
			(accounts["1200"], 30000, 0),
			(accounts["1548"], 1900, 0),
			(accounts["1790"], 0, 6900),
			(accounts["0800"], 0, 25000),
		],
		is_opening="Yes",
	)


def vat_return(company: str, year: int, month: int):
	return frappe.get_doc(
		{
			"doctype": "VAT Return",
			"company": company,
			"year": year,
			"rhythm": "monthly",
			"period_index": month,
		}
	)


class FirstYearTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for year in (2025, 2026):
			ensure_fiscal_year(COMPANY, date(year, 6, 30))
		make_company(COMPANY, "STEJ")
		cls.accounts = accounts = accounts_of(COMPANY)
		make_settings(
			COMPANY,
			[(2025, "monthly", 1)],
			books_start=BOOKS_START,
			zm_rules=[{"year": 2025, "valid_from_month": 1, "rhythm": "monthly", "services_monthly": 1}],
		)
		make_mapping(COMPANY)
		open_books(COMPANY, accounts, "2026-01-01")
		# January moves the Vorsteuer carried in to the Vorsteuer deductible now.
		post_journal_entry(COMPANY, "2026-01-15", [(accounts["1576"], 1900, 0), (accounts["1548"], 0, 1900)])

		make_company(NEW_COMPANY, "STEE")
		new_accounts = accounts_of(NEW_COMPANY)
		make_settings(NEW_COMPANY, [(2026, "monthly", 1)])
		make_mapping(NEW_COMPANY)
		open_books(NEW_COMPANY, new_accounts, "2026-01-01")

		make_company(DECEMBER_COMPANY, "STED")
		open_books(DECEMBER_COMPANY, accounts_of(DECEMBER_COMPANY), "2025-12-31")

	def setUp(self):
		frappe.db.savepoint("first_year_test")
		self.addCleanup(frappe.db.rollback, save_point="first_year_test")

	def test_a_voranmeldung_before_the_start_is_refused(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "Dezember 2025 begins before the start of the books"
		):
			vat_return(COMPANY, 2025, 12).insert()

	def test_january_releases_the_vorsteuer_carried_in_and_is_ready(self):
		"""The rehearsal with real books: „Vorsteuer in Folgeperiode/im Folgejahr abziehbar“ carries a balance over the
		turn of the year, and January releases it. The opening entry itself stays out of the Voranmeldung."""
		doc = vat_return(COMPANY, 2026, 1).insert()
		doc.calculate()
		doc.reload()
		self.assertEqual([row.account_number for row in doc.unmapped], [])
		self.assertEqual((doc.status, doc.ready), ("Bereit", 1))
		amounts = {row.kennzahl: Decimal(str(row.amount)) for row in doc.kennzahlen}
		self.assertEqual(amounts["66"], Decimal("1900"))
		self.assertEqual(amounts["83"], Decimal("-1900"))
		texts = [row.text for row in doc.hints]
		self.assertTrue(any(text.startswith("Konto 1548 ") and "löst 1.900,00 €" in text for text in texts))
		self.assertTrue(
			any(
				text.startswith("Vor dem Start der Bücher in Steuerbote: Der Vergleich mit Dezember 2025")
				for text in texts
			)
		)

	def test_a_new_balance_on_the_timing_account_still_blocks(self):
		post_journal_entry(
			COMPANY, "2026-02-10", [(self.accounts["1548"], 500, 0), (self.accounts["1200"], 0, 500)]
		)
		doc = vat_return(COMPANY, 2026, 2).insert()
		doc.calculate()
		doc.reload()
		self.assertEqual([row.account_number for row in doc.unmapped], ["1548"])
		self.assertEqual(doc.status, "Berechnet")

	def test_a_zusammenfassende_meldung_before_the_start_is_refused(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "Dezember 2025 begins before the start of the books"
		):
			frappe.get_doc(
				{
					"doctype": "Recapitulative Statement",
					"company": COMPANY,
					"year": 2025,
					"period_kind": "month",
					"period_index": 12,
				}
			).insert()

	def test_no_deadline_before_the_start(self):
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		found = deadlines.deadlines_of(COMPANY, settings, date(2026, 1, 5), 40)
		self.assertEqual(
			{item.period_label for item in found if item.kind.name == "VORANMELDUNG"}, {"Januar 2026"}
		)

	def test_the_annual_accounts_take_no_previous_year_from_opening_entries(self):
		for company in (COMPANY, DECEMBER_COMPANY):
			with self.subTest(company=company):
				year = balances.fiscal_year_books(
					company, frappe.db.get_value("Fiscal Year", {"year_start_date": "2026-01-01"})
				)
				self.assertIsNone(year.prior)

	def test_the_first_income_tax_returns_take_the_carry_forwards_of_the_last_notices(self):
		self.assertTrue(income_tax_sources.first_year(COMPANY, "Corporate Income Tax Return", 2026))
		self.assertFalse(income_tax_sources.first_year(DECEMBER_COMPANY, "Corporate Income Tax Return", 2026))

	def test_the_setup_sets_the_start_and_names_what_is_left(self):
		context = setup.SetupContext(NEW_COMPANY, date(2026, 1, 20), None, {})
		result = setup.check_books_start(context)
		self.assertEqual(result.outcome, Outcome.CREATED)
		self.assertEqual(frappe.db.get_value("VAT Return Settings", NEW_COMPANY, "books_start"), BOOKS_START)
		templates = {note.template: note for note in result.notes}
		self.assertTrue(templates[setup.START_PROPOSED].open)
		self.assertFalse(templates[start.OPENING_FLAGGED].open)
		missing = templates[start.PRIOR_MISSING]
		self.assertTrue(missing.open)
		self.assertTrue(missing.values[0].startswith("Januar 2025, Februar 2025"))
		self.assertTrue(templates[start.ANNUAL_SETTINGS_MISSING].open)

	def test_the_proposal_of_the_filing_period_takes_the_year_filed_before(self):
		for month in range(1, 13):
			frappe.get_doc(
				{
					"doctype": "VAT Return Prior Filing",
					"company": NEW_COMPANY,
					"year": 2025,
					"rhythm": "monthly",
					"period_index": month,
					"filed_on": "2025-12-20",
					"kz83": 1000,
					"source_document": "Übermittlungsprotokoll",
					"reason": "Vor Steuerbote abgegeben",
				}
			).insert().submit()
		self.assertEqual(len(prior_filings.prior_filings(NEW_COMPANY, {2025})), 12)
		settings = frappe.get_doc("VAT Return Settings", NEW_COMPANY)
		settings.set("period_rules", [])
		settings.flags.ignore_mandatory = True
		settings.flags.ignore_validate = True
		settings.save()
		context = setup.SetupContext(NEW_COMPANY, date(2026, 1, 20), None, {})
		result = setup.propose_filing_period(context)
		self.assertEqual(result.outcome, Outcome.CREATED)
		self.assertEqual(result.notes[0].template, setup.PROPOSED_FROM_PRIOR)
		self.assertEqual(result.notes[0].values[2:], (2025, Decimal("12000.00")))
