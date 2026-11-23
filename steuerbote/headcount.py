"""The Arbeitnehmer of a company for its size class: the employees of ERPNext on the quarter ends of § 267 Abs. 5 HGB.

„Als durchschnittliche Zahl der Arbeitnehmer gilt der vierte Teil der Summe aus den Zahlen der jeweils am 31. März,
30. Juni, 30. September und 31. Dezember beschäftigten Arbeitnehmer einschließlich der im Ausland beschäftigten
Arbeitnehmer, jedoch ohne die zu ihrer Berufsausbildung Beschäftigten.“ (§ 267 Abs. 5 HGB) An Employee of the company
counts on a day from its Date of Joining to its Relieving Date, both included, whatever its status, which ERPNext keeps
for today only. HRMS adds the Employment Type (the custom field employment_type of hrms/setup.py, with Apprentice and
Intern among its records); the Annual Filing Settings name the types that do not count (employment_types_not_counted),
such as Apprentice. Without HRMS the employees carry no type, and every one counts. Who counts beyond the law, a
part-timer as one head and a Geschäftsführer, stays unverified (steuerbote.hgb.size.HEADCOUNT_CONVENTIONS), which the
Arbeitnehmer by hand of the Annual Accounts answer with a reason.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import frappe
from frappe.utils import getdate

from steuerbote.steuerbote.doctype.annual_accounts.bridge import Employee, average_employees, headcounts

EMPLOYEE = "Employee"
EMPLOYMENT_TYPE = "employment_type"


@dataclass(frozen=True)
class Headcount:
	"""The employees on each quarter end, their average, and whether the employees carry an Employment Type."""

	counts: dict[date, int]
	average: Decimal
	typed: bool


def has_employment_type() -> bool:
	"""Whether the Employee has the Employment Type of HRMS."""
	return frappe.get_meta(EMPLOYEE).has_field(EMPLOYMENT_TYPE)


def employees(company: str) -> tuple[Employee, ...]:
	"""The employees of the company with the days of joining and leaving, and their Employment Type where HRMS adds
	it."""
	typed = has_employment_type()
	fields = ["date_of_joining", "relieving_date", *((EMPLOYMENT_TYPE,) if typed else ())]
	rows = frappe.get_all(
		EMPLOYEE,
		filters={"company": company, "date_of_joining": ["is", "set"]},
		fields=fields,
		order_by="date_of_joining, name",
	)
	return tuple(
		Employee(
			getdate(row.date_of_joining),
			getdate(row.relieving_date) if row.relieving_date else None,
			(row.get(EMPLOYMENT_TYPE) or "").strip(),
		)
		for row in rows
	)


def count(company: str, closing_date: date, not_counted: Collection[str]) -> Headcount:
	"""The headcount of the fiscal year that ends on ``closing_date``, without the Employment Types not counted."""
	counts = headcounts(employees(company), closing_date, set(not_counted))
	return Headcount(counts, average_employees(counts, closing_date), has_employment_type())
