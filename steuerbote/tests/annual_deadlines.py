"""Annual documents for the Frappe tests of the annual deadlines: the report Offene Fristen and the daily reminder.

The DocTypes of the annual filings come with their modules, so the tests read the annual deadlines from DocTypes of
their own, put in place of those of the registry (steuerbote.deadlines.annual.DOCTYPES) while a test runs: the test
documents of the base of the annual documents (steuerbote/tests/annual_document.py), Steuerbote Test Annual Filing for
the three Erklärungen and Steuerbote Test Annual Accounts for the Jahresabschluss, and Steuerbote Test Electronic
Balance Sheet, a custom DocType with the standard fields of an annual document and the Bilanzart, for the E-Bilanz.
The tests write their documents and ELSTER Transmissions as the site keeps them, past the controllers, since the
deadlines only read them. All names are invented.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

import frappe

from steuerbote.deadlines import annual
from steuerbote.deadlines.annual import AnnualDocType
from steuerbote.deadlines.obligations import Kind
from steuerbote.jahresmeldung.lifecycle import FILING, standard_fields
from steuerbote.tests import annual_document
from steuerbote.tests.annual_document import ADDRESS
from steuerbote.tests.helpers import insert_record, make_company

BALANCE_SHEET = "Steuerbote Test Electronic Balance Sheet"
FILING_DOCTYPE = annual_document.DOCTYPE
ACCOUNTS_DOCTYPE = annual_document.ACCOUNTS_DOCTYPE
TEST_DOCTYPES = MappingProxyType(
	{
		FILING_DOCTYPE: AnnualDocType(
			(
				Kind.UMSATZSTEUERERKLAERUNG,
				Kind.KOERPERSCHAFTSTEUERERKLAERUNG,
				Kind.GEWERBESTEUERERKLAERUNG,
			)
		),
		BALANCE_SHEET: AnnualDocType((Kind.E_BILANZ,), opening_balance_field=annual.OPENING_BALANCE_FIELD),
		ACCOUNTS_DOCTYPE: AnnualDocType((Kind.FESTSTELLUNG, Kind.OFFENLEGUNG)),
	}
)
TRANSMISSION = "ELSTER Transmission"


def balance_sheet_definition() -> dict[str, Any]:
	"""The test DocType of the E-Bilanz: the standard fields of the lifecycle FILING and the Bilanzart."""
	fields = [
		{
			"fieldname": field.fieldname,
			"fieldtype": field.fieldtype,
			"label": field.label,
			"options": field.options,
			"read_only": int(field.read_only),
			"reqd": int(field.reqd),
		}
		for field in standard_fields(FILING, BALANCE_SHEET, transmits=True)
	]
	fields.append(
		{
			"fieldname": annual.OPENING_BALANCE_FIELD,
			"fieldtype": "Select",
			"label": "Statement Type",
			"options": f"Jahresabschluss\n{annual.OPENING_BALANCE}",
		}
	)
	return {
		"doctype": "DocType",
		"name": BALANCE_SHEET,
		"module": "Steuerbote",
		"custom": 1,
		"is_submittable": 1,
		"autoname": "hash",
		"fields": fields,
		"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "submit": 1}],
	}


def install() -> None:
	"""Make the test DocTypes once per site. Making a DocType ends the transaction, so a test class calls this
	before it writes anything else."""
	annual_document.install()
	if not frappe.db.exists("DocType", BALANCE_SHEET):
		frappe.get_doc(balance_sheet_definition()).insert(ignore_permissions=True)


@contextmanager
def use_test_doctypes() -> Iterator[None]:
	"""While it lasts, the test DocTypes file the annual deadlines in place of those of the registry."""
	with patch.object(annual, "DOCTYPES", TEST_DOCTYPES):
		yield


def make_annual_company(company: str, abbr: str, since: str, **fields: Any) -> str:
	"""A company with Annual Filing Settings made on the day ``since``; ``fields`` go to the settings."""
	make_company(company, abbr)
	frappe.get_doc(
		{"doctype": "Annual Filing Settings", "company": company, "legal_form": "GmbH", **ADDRESS, **fields}
	).insert(ignore_permissions=True)
	frappe.db.set_value("Annual Filing Settings", company, "creation", since, update_modified=False)
	return company


def insert_annual(
	doctype: str, company: str, status: str, docstatus: int = 0, year: int = 2026, **fields: Any
) -> str:
	"""An annual document as the site keeps it, past its controller."""
	return insert_record(doctype, company=company, year=year, status=status, docstatus=docstatus, **fields)


def insert_transmission(
	doctype: str, document: str, status: str, finished_at: str, operation: str = "send"
) -> str:
	"""A real run of the document through Steuerbote, as the site keeps it."""
	return insert_record(
		TRANSMISSION,
		document_type=doctype,
		document=document,
		operation=operation,
		status=status,
		simulated=0,
		started_at=finished_at,
		finished_at=finished_at,
	)
