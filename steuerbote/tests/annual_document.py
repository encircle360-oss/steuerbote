"""Small annual documents for the Frappe tests of the base of the annual documents,
steuerbote/steuerbote/annual_filing.py.

The DocTypes of the annual filings come with their modules, so the tests of the base make DocTypes of their own while
they run: Steuerbote Test Annual Filing, a custom DocType with the standard fields of the lifecycle FILING
(steuerbote.jahresmeldung.lifecycle.standard_fields), a table of lines and a few fields of its own, and its child
Steuerbote Test Annual Filing Line; and Steuerbote Test Annual Accounts, with the standard fields of the lifecycle
ACCOUNTS of the Jahresabschluss and the same lines, which goes to no Finanzamt. A custom DocType has no controller of
its own, Frappe gives it Document (import_controller in frappe/model/document.py), so use_controller() lets
frappe.get_doc take TestAnnualFiling and TestAnnualAccounts for them while a test runs, and lets the ELSTER
Transmission name the first.

Berechnen of a test document reads its field source, JSON such as [{"key": "A", "label": "Umsätze", "computed":
"100.00"}], where an entry with "finding" is a finding of the sources; check_reported finds an error on a line that
reports less than zero, so that a correction changes what Berechnen checked. The test document of FILING goes to
ELSTER as the Körperschaftsteuererklärung of its year with an empty KSt1, whose schema ERiC 44.3.6.0 does not have
yet; under structure_only() the simulation checks its structure and its Vorsatz without the rules of the Vordrucke of
the year (steuerbote.eric.simulation.kst), which refuse an empty KSt1. With the kind Bilanz it goes as the E-Bilanz
of taxonomy 6.9, in the frame of ebilanz_000002.xsd around an instance without facts, which structure_only() checks
for its frame alone. All names, numbers and addresses are invented.
"""

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

import frappe
import frappe.model.document
from frappe.model.document import Document
from frappe.utils import cint, getdate
from lxml import etree

from steuerbote.elster import vorsatz
from steuerbote.eric import datenart, fake
from steuerbote.eric.simulation import bilanz as bilanz_checks
from steuerbote.eric.simulation import erklaerung
from steuerbote.eric.simulation import kst as kst_checks
from steuerbote.jahresmeldung import overrides
from steuerbote.jahresmeldung.findings import Finding, Severity
from steuerbote.jahresmeldung.lifecycle import ACCOUNTS, FILING, Lifecycle, standard_fields
from steuerbote.steuerbote.annual_filing import AnnualFiling, Calculation
from steuerbote.steuerbote.doctype.elster_transmission import elster_transmission, transmission
from steuerbote.steuerbote.doctype.elster_transmission.transmission import TRANSMISSION, Transmittable
from steuerbote.tests.helpers import ensure_fiscal_year, make_company, make_settings

DOCTYPE = "Steuerbote Test Annual Filing"
ACCOUNTS_DOCTYPE = "Steuerbote Test Annual Accounts"
LINE_DOCTYPE = "Steuerbote Test Annual Filing Line"
COMPANY = "Steuerbote Test Jahresmeldung GmbH"
ABBR = "STJM"
TAXONOMY = "6.9"
NEGATIVE = "SB-TEST-NEGATIV"
LINES = (
	{"key": "A", "label": "Umsätze", "computed": "100.00"},
	{"key": "B", "label": "Vorsteuer", "computed": "30.00"},
)
DATENLIEFERANT = {
	"filer_name": COMPANY,
	"street": "Musterweg 12a",
	"postal_code": "80331",
	"city": "München",
	"phone": "089 1234567",
	"email": "buchhaltung@example.org",
}
ADDRESS = {
	"street": "Musterweg",
	"house_number": "12",
	"house_number_suffix": "a",
	"address_supplement": "Hinterhaus",
	"postal_code": "80331",
	"city": "München",
	"country": "Germany",
}


def _field(fieldname: str, fieldtype: str, label: str, options: str | None = None, **flags: Any) -> dict:
	return {"fieldname": fieldname, "fieldtype": fieldtype, "label": label, "options": options, **flags}


def _standard_fields(lifecycle: Lifecycle, doctype: str, *, transmits: bool) -> list[dict]:
	return [
		_field(
			field.fieldname,
			field.fieldtype,
			field.label,
			field.options,
			read_only=int(field.read_only),
			reqd=int(field.reqd),
			set_only_once=int(field.set_only_once),
		)
		for field in standard_fields(lifecycle, doctype, transmits=transmits)
	]


def _lines_and_amendment(doctype: str) -> list[dict]:
	"""The fields of its own that both test documents have: the sources, what Berechnen read, the total of the lines as
	filed, the lines and the link of an amendment."""
	return [
		_field("source", "Small Text", "Source"),
		_field("lines_read", "Int", "Lines Read", read_only=1),
		_field("total", "Currency", "Total", read_only=1),
		_field("lines", "Table", "Lines", LINE_DOCTYPE),
		_field("amended_from", "Link", "Amended From", doctype, read_only=1, no_copy=1, print_hide=1),
	]


def _doctype(name: str, fields: list[dict]) -> dict[str, Any]:
	return {
		"doctype": "DocType",
		"name": name,
		"module": "Steuerbote",
		"custom": 1,
		"is_submittable": 1,
		"autoname": "hash",
		"fields": fields,
		"permissions": [
			{
				"role": "System Manager",
				"read": 1,
				"write": 1,
				"create": 1,
				"submit": 1,
				"cancel": 1,
				"amend": 1,
				"delete": 1,
			}
		],
	}


def definition() -> dict[str, Any]:
	"""The test document of the lifecycle FILING: the standard fields, then the fields of its own."""
	return _doctype(
		DOCTYPE,
		[
			*_standard_fields(FILING, DOCTYPE, transmits=True),
			_field("kind", "Select", "Kind", "KSt\nBilanz", default="KSt"),
			_field("revision_status", "Select", "Revision Status", "\nE\nB\nG\nBG\nsK\nI\nK"),
			*_lines_and_amendment(DOCTYPE),
		],
	)


def accounts_definition() -> dict[str, Any]:
	"""The test document of the lifecycle ACCOUNTS: the standard fields, then the fields of its own."""
	return _doctype(
		ACCOUNTS_DOCTYPE,
		[
			*_standard_fields(ACCOUNTS, ACCOUNTS_DOCTYPE, transmits=False),
			*_lines_and_amendment(ACCOUNTS_DOCTYPE),
		],
	)


def line_definition() -> dict[str, Any]:
	return {
		"doctype": "DocType",
		"name": LINE_DOCTYPE,
		"module": "Steuerbote",
		"custom": 1,
		"istable": 1,
		"fields": [
			_field("key", "Data", "Key"),
			_field("label", "Data", "Label", read_only=1),
			_field("computed", "Currency", "Computed", read_only=1),
			_field("correction", "Currency", "Correction"),
			_field("correction_reason", "Small Text", "Reason"),
			_field("reported", "Currency", "Reported", read_only=1),
			_field("manual", "Check", "Manual", read_only=1),
		],
	}


def install() -> None:
	"""Make the DocTypes of the test documents once per site; like those of Frappe's own tests, they stay."""
	for record in (line_definition(), definition(), accounts_definition()):
		if not frappe.db.exists("DocType", record["name"]):
			frappe.get_doc(record).insert(ignore_permissions=True)


def make_company_with_settings() -> None:
	"""The company of the tests with its VAT Return Settings, Annual Filing Settings and Fiscal Years 2026 and 2027."""
	make_company(COMPANY, ABBR)
	if not frappe.db.exists("VAT Return Settings", COMPANY):
		make_settings(COMPANY, [(2026, "monthly", 1)], **DATENLIEFERANT)
	for year in (2026, 2027):
		ensure_fiscal_year(COMPANY, date(year, 6, 30))
	if not frappe.db.exists("Annual Filing Settings", COMPANY):
		frappe.get_doc(
			{"doctype": "Annual Filing Settings", "company": COMPANY, "legal_form": "GmbH", **ADDRESS}
		).insert(ignore_permissions=True)


@contextmanager
def use_controller() -> Iterator[None]:
	"""While it lasts, frappe.get_doc takes TestAnnualFiling and TestAnnualAccounts for the test documents, and the
	ELSTER Transmission records the runs of the first."""
	original = frappe.model.document.get_controller
	controllers = {DOCTYPE: TestAnnualFiling, ACCOUNTS_DOCTYPE: TestAnnualAccounts}

	def controller(doctype: str):
		return controllers.get(doctype) or original(doctype)

	documents = (*elster_transmission.DOCUMENT_TYPES, DOCTYPE)
	with (
		patch.object(frappe.model.document, "get_controller", controller),
		patch.object(elster_transmission, "DOCUMENT_TYPES", documents),
		patch.object(transmission, "DOCUMENT_TYPES", documents),
	):
		yield


@contextmanager
def structure_only() -> Iterator[None]:
	"""While it lasts, the simulation checks a Körperschaftsteuererklärung for its structure and its Vorsatz alone, and
	an E-Bilanz for its frame without the rules of its instance (steuerbote.eric.simulation.bilanz)."""
	structure = erklaerung.checks(kst_checks.TITLE, kst_checks.MAIN_FORM)
	checks = {datenart.kst(2026).name: structure, datenart.bilanz(TAXONOMY).name: bilanz_checks.FRAME}
	with patch.object(fake, "CHECKS", MappingProxyType({**fake.CHECKS, **checks})):
		yield


def discard_all() -> None:
	"""Take the test documents out with their ELSTER Transmissions: a filed one cannot be cancelled, so it leaves the
	database directly, and its key is free for the next test."""
	frappe.db.delete(TRANSMISSION, {"document_type": DOCTYPE})
	for doctype in (DOCTYPE, ACCOUNTS_DOCTYPE):
		for name in frappe.get_all(doctype, pluck="name"):
			frappe.db.set_value(doctype, name, "docstatus", 2, update_modified=False)
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def source(*entries: Mapping[str, Any]) -> str:
	"""The field source of a test document: its lines and the findings of its sources."""
	return json.dumps(list(entries))


class TestDocument:
	"""What both test documents compute from their field source, and how they sum up their lines."""

	LINES = "lines"
	LINE_COLUMNS = overrides.Columns(key="key", amounts=("computed",), described=("label",))
	CALCULATED_FIELDS = ("lines_read",)

	def compute(self) -> Calculation:
		entries = json.loads(self.source or "[]")
		lines = [
			{"key": entry["key"], "label": entry.get("label", ""), "computed": Decimal(entry["computed"])}
			for entry in entries
			if "finding" not in entry
		]
		found = [
			Finding(entry["finding"], entry["severity"], entry["text"], entry.get("reference", ""))
			for entry in entries
			if "finding" in entry
		]
		return Calculation(lines=lines, values={"lines_read": len(lines)}, findings=found)

	def check_reported(self, lines: Sequence[Mapping[str, Any]]) -> Sequence[Finding]:
		return [
			Finding(
				NEGATIVE, Severity.ERROR, f"Die Zeile {line['key']} meldet weniger als null.", line["key"]
			)
			for line in lines
			if line["reported"] < 0
		]

	def compute_deadline(self) -> date:
		return date(cint(self.year) + 1, 7, 31)

	def set_amounts(self) -> None:
		self.total = self._total()

	def amounts_kept(self, stored: Document) -> bool:
		return overrides.to_amount(stored.total) == self._total()

	def _total(self) -> Decimal:
		return sum(
			(overrides.reported(row.as_dict(), self.LINE_COLUMNS) for row in self.lines), Decimal("0.00")
		)


class TestAnnualFiling(TestDocument, AnnualFiling, Transmittable, Document):
	def correction_values(self) -> dict[str, Any]:
		return {"kind": self.kind, "source": self.source}

	def datenart(self) -> datenart.Datenart:
		return datenart.bilanz(TAXONOMY) if self.kind == "Bilanz" else datenart.kst(cint(self.year))

	def nutzdaten(self, hersteller_id: str) -> str:
		kind = self.datenart()
		if kind.name == "Bilanz":
			return (
				f'<EBilanz xmlns="{kind.namespace}" version="{kind.root_version}">'
				f"<stichtag>{getdate(self.to_date):%Y%m%d}</stichtag>"
				'<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"/></EBilanz>'
			)
		root = etree.Element(f"{{{kind.namespace}}}{kind.root}", nsmap={None: kind.namespace})
		root.set("version", kind.root_version)
		etree.SubElement(root, f"{{{kind.namespace}}}KSt1")
		vorsatz.append_to(root, kind, self.vorsatz())
		return etree.tostring(root, encoding="unicode")


class TestAnnualAccounts(TestDocument, AnnualFiling, Document):
	LIFECYCLE = ACCOUNTS
