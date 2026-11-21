"""The report Offene Fristen on a site: the deadlines of a company from its settings, its documents, its holidays
and its ledger, by due date, with links to the documents, and without the filter those of every company the user
may read."""

from datetime import date

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.steuerbote.report.offene_fristen.offene_fristen import execute
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	make_user,
	post_journal_entry,
)

# Files the Voranmeldung and the Zusammenfassende Meldung monthly from 2026, keeps its filings in Steuerbote since
# 1 November 2026, delivered goods to another member state in October, and its Holiday List holds 10 December.
COMPANY = "Steuerbote Test Fristenbericht GmbH"
# Has no VAT Return Settings, so it has no deadlines.
OTHER_COMPANY = "Steuerbote Test Fristenbericht ohne Einstellungen GmbH"
# May read only the other company.
ACCOUNTANT = "steuerbote-fristen-buchhaltung@example.com"
# A Friday.
TODAY = "2026-11-20 09:00:00"
ACCOUNTS = {
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}
VA = "Umsatzsteuer-Voranmeldung"
ZM = "Zusammenfassende Meldung"


def new_vat_return(month: int, **fields):
	return frappe.get_doc(
		{
			"doctype": "VAT Return",
			"company": COMPANY,
			"year": 2026,
			"rhythm": "monthly",
			"period_index": month,
			"remarks": "Testabgabe",
			**fields,
		}
	).insert()


def filed_vat_return(month: int):
	doc = new_vat_return(month)
	doc.calculate()
	doc.reload()
	doc.mark_filed_outside("In Mein ELSTER abgegeben")
	return doc


class TestOffeneFristen(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STOF")
		make_company(OTHER_COMPANY, "STOO")
		cls.account = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(
			COMPANY,
			[(2026, "monthly", 1)],
			zm_rules=[{"year": 2026, "valid_from_month": 1, "rhythm": "monthly"}],
		)
		frappe.db.set_value(
			"VAT Return Settings", COMPANY, "creation", "2026-11-01 08:00:00", update_modified=False
		)
		make_mapping(COMPANY)
		post_journal_entry(
			COMPANY, "2026-10-15", [(cls.account["1400"], 1000, 0), (cls.account["8125"], 0, 1000)]
		)
		holidays = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": "Steuerbote Test Fristenbericht 2026",
				"from_date": "2026-01-01",
				"to_date": "2026-12-31",
				"holidays": [{"holiday_date": "2026-12-10", "description": "Testtag"}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Company", COMPANY, "default_holiday_list", holidays.name)

	def setUp(self):
		frappe.db.savepoint("offene_fristen_test")
		self.addCleanup(frappe.db.rollback, save_point="offene_fristen_test")

	def report(self, **filters) -> tuple[list[dict], list[dict]]:
		with self.freeze_time(TODAY):
			return execute({"company": COMPANY, "horizon": 30, **filters})

	def rows(self, **filters) -> list[dict]:
		return self.report(**filters)[1]

	def deadlines(self, **filters) -> list[tuple]:
		return [
			(row["kind"], row["period_label"], row["due"], row["days"], row["status"])
			for row in self.rows(**filters)
		]

	def test_lists_the_deadlines_of_the_company_by_due_date(self):
		self.assertEqual(
			self.deadlines(),
			[
				(VA, "Oktober 2026", date(2026, 11, 10), -10, "Fehlt"),
				(ZM, "Oktober 2026", date(2026, 11, 25), 5, "Fehlt"),
				(VA, "November 2026", date(2026, 12, 11), 21, "Fehlt"),
			],
		)
		self.assertEqual({row["company"] for row in self.rows()}, {COMPANY})

	def test_every_row_fills_the_columns(self):
		columns, rows = self.report()
		fieldnames = [column["fieldname"] for column in columns]
		self.assertEqual(fieldnames, ["company", "kind", "period_label", "due", "days", "status", "document"])
		self.assertTrue(rows)
		for row in rows:
			self.assertEqual(set(row), set(fieldnames))

	def test_a_missing_deadline_links_a_new_document_of_its_period(self):
		october = self.rows()[0]
		self.assertEqual(
			october["document"],
			'<a href="/desk/vat-return/new?company=Steuerbote+Test+Fristenbericht+GmbH&amp;year=2026'
			'&amp;rhythm=monthly&amp;period_index=10">Create Document</a>',
		)

	def test_a_draft_keeps_its_deadline_open_and_links_it(self):
		draft = new_vat_return(11)
		november = self.rows()[-1]
		self.assertEqual(
			(november["status"], november["document"]),
			("Offen", f'<a href="/desk/vat-return/{draft.name}">{draft.name}</a>'),
		)

	def test_a_filed_return_files_its_deadline(self):
		filed_vat_return(10)
		self.assertNotIn((VA, "Oktober 2026"), [row[:2] for row in self.deadlines()])
		november = filed_vat_return(11)
		self.assertEqual(self.deadlines()[-1], (VA, "November 2026", date(2026, 12, 11), 21, "Abgegeben"))
		self.assertIn(f">{november.name}</a>", self.rows()[-1]["document"])

	def test_a_return_sent_but_not_submitted_files_its_deadline(self):
		"""ELSTER accepted the return and its submission failed afterwards: the Finanzamt has it, on the day the
		transmission finished, while the return stays a draft."""
		draft = new_vat_return(11)
		with self.freeze_time("2026-11-18 10:00:00"):
			draft.new_transmission("send", simulated=False, status="Erfolgreich")
		self.assertEqual(self.deadlines()[-1], (VA, "November 2026", date(2026, 12, 11), 21, "Abgegeben"))
		self.assertIn(f">{draft.name}</a>", self.rows()[-1]["document"])

	def test_a_meldezeitraum_without_anything_to_report_owes_no_zusammenfassende_meldung(self):
		self.assertNotIn((ZM, "November 2026"), [row[:2] for row in self.deadlines(horizon=40)])
		post_journal_entry(
			COMPANY, "2026-11-05", [(self.account["1400"], 500, 0), (self.account["8125"], 0, 500)]
		)
		self.assertIn((ZM, "November 2026", date(2026, 12, 25), 35, "Fehlt"), self.deadlines(horizon=40))

	def test_without_a_horizon_looks_sixty_days_ahead(self):
		self.assertEqual(self.deadlines(horizon=None)[-1][:3], (VA, "Dezember 2026", date(2027, 1, 11)))

	def test_refuses_a_horizon_before_today(self):
		with self.assertRaisesRegex(frappe.ValidationError, "number of days"):
			self.report(horizon=-1)

	def test_without_a_company_lists_every_company_with_settings_by_due_date(self):
		rows = self.rows(company=None)
		self.assertIn(COMPANY, {row["company"] for row in rows})
		self.assertNotIn(OTHER_COMPANY, {row["company"] for row in rows})
		self.assertEqual([row["due"] for row in rows], sorted(row["due"] for row in rows))
		self.assertEqual(self.rows(company=OTHER_COMPANY), [])

	def test_shows_a_user_only_the_companies_the_user_may_read(self):
		user = make_user(ACCOUNTANT, "Accounts User")
		frappe.get_doc(
			{"doctype": "User Permission", "user": user, "allow": "Company", "for_value": OTHER_COMPANY}
		).insert(ignore_permissions=True)
		with self.set_user(user):
			self.assertNotIn(COMPANY, {row["company"] for row in self.rows(company=None)})
			with self.assertRaises(frappe.PermissionError):
				self.rows()
