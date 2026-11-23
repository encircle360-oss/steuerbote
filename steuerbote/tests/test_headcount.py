"""steuerbote/headcount.py on the Frappe test site: the employees of a company on the quarter ends of § 267 Abs. 5 HGB,
from the day of joining to the day of leaving, without the Employment Types the Annual Filing Settings leave out, and
every employee where the Employee has no Employment Type, as without HRMS. Every name and day is invented."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote import headcount
from steuerbote.steuerbote.doctype.annual_accounts.bridge import Employee
from steuerbote.tests import annual_accounts as data
from steuerbote.tests.helpers import make_company

COMPANY = data.Company("Steuerbote Test Arbeitnehmer GmbH", "STAN", "99903", ())
NEIGHBOUR = data.Company("Steuerbote Test Arbeitnehmer Nachbar GmbH", "STAO", "99904", ())
CLOSING = date(2026, 12, 31)


class TestHeadcount(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		data.employment_type_field()
		for company in (COMPANY, NEIGHBOUR):
			make_company(company.name, company.abbr)

	def setUp(self):
		super().setUp()
		for company in (COMPANY, NEIGHBOUR):
			self.addCleanup(frappe.db.delete, data.EMPLOYEE, {"company": company.name})
		data.employ(COMPANY, 1, "2025-01-01")
		data.employ(COMPANY, 2, "2026-07-01")
		data.employ(COMPANY, 3, "2025-08-01", kind="Apprentice")
		data.employ(COMPANY, 4, "2025-01-01", relieved="2026-04-30")
		data.employ(NEIGHBOUR, 1, "2025-01-01")

	def test_reads_the_days_of_joining_and_leaving_and_the_employment_type_of_the_company(self):
		self.assertTrue(headcount.has_employment_type())
		self.assertEqual(
			headcount.employees(COMPANY.name),
			(
				Employee(date(2025, 1, 1), None, ""),
				Employee(date(2025, 1, 1), date(2026, 4, 30), ""),
				Employee(date(2025, 8, 1), None, "Apprentice"),
				Employee(date(2026, 7, 1), None, ""),
			),
		)

	def test_counts_each_quarter_end_without_the_types_not_counted(self):
		counted = headcount.count(COMPANY.name, CLOSING, ["Apprentice"])
		self.assertEqual(
			counted.counts,
			{date(2026, 3, 31): 2, date(2026, 6, 30): 1, date(2026, 9, 30): 2, date(2026, 12, 31): 2},
		)
		self.assertEqual((counted.average, counted.typed), (Decimal("1.75"), True))
		self.assertEqual(headcount.count(COMPANY.name, CLOSING, []).average, Decimal("2.75"))

	def test_without_the_employment_type_every_employee_counts(self):
		with patch.object(headcount, "has_employment_type", return_value=False):
			counted = headcount.count(COMPANY.name, CLOSING, ["Apprentice"])
			employees = headcount.employees(COMPANY.name)
		self.assertEqual({employee.employment_type for employee in employees}, {""})
		self.assertEqual((counted.average, counted.typed), (Decimal("2.75"), False))
