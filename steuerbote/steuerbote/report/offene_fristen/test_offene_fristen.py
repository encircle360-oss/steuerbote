"""The report Offene Fristen on a site: the deadlines of a company from its settings, its documents, its holidays
and its ledger, by due date, with links to the documents, and without the filter those of every company the user
may read; and the annual deadlines of a company with Annual Filing Settings, read from the annual documents the site
has."""

from datetime import date
from types import MappingProxyType
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.deadlines import annual
from steuerbote.deadlines.annual import AnnualDocType
from steuerbote.deadlines.obligations import Kind
from steuerbote.steuerbote.deadlines import annual_deadline
from steuerbote.steuerbote.report.offene_fristen.offene_fristen import execute
from steuerbote.tests import annual_deadlines
from steuerbote.tests.annual_deadlines import (
	ACCOUNTS_DOCTYPE,
	BALANCE_SHEET,
	FILING_DOCTYPE,
	insert_annual,
	insert_transmission,
	make_annual_company,
)
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
SVZ = "Sondervorauszahlung"


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
		self.assertEqual(
			fieldnames,
			[
				"company",
				"kind",
				"period_label",
				"due",
				"days",
				"status",
				"document",
				"document_status",
				"note",
			],
		)
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
		self.assertEqual((november["document_status"], november["note"]), ("Entwurf", ""))
		self.assertEqual((self.rows()[0]["document_status"], self.rows()[0]["note"]), ("", ""))

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

	def test_a_zusammenfassende_meldung_sent_but_not_submitted_files_its_deadline(self):
		"""ELSTER accepted the statement, or the outcome of its Senden is unknown, while it stayed a draft or was
		discarded: the BZSt has it, or may have it."""
		draft = frappe.get_doc(
			{
				"doctype": "Recapitulative Statement",
				"company": COMPANY,
				"year": 2026,
				"period_kind": "month",
				"period_index": 10,
			}
		).insert()
		october = (ZM, "Oktober 2026", date(2026, 11, 25), 5)
		self.assertIn((*october, "Offen"), self.deadlines())
		for status in ("Erfolgreich", "Unbekannt"):
			with self.subTest(status=status):
				frappe.db.delete("ELSTER Transmission", {"document": draft.name})
				draft.new_transmission("send", simulated=False, status=status)
				self.assertIn((*october, "Abgegeben"), self.deadlines())
		frappe.db.set_value("Recapitulative Statement", draft.name, "docstatus", 2)
		self.assertIn((*october, "Abgegeben"), self.deadlines())

	def test_a_dauerfristverlaengerung_sent_but_not_submitted_files_its_deadline(self):
		"""ELSTER accepted the form, or the outcome of its Senden is unknown, while it stayed a draft or was
		discarded: the Finanzamt has it, or may have it."""
		settings = frappe.get_doc("VAT Return Settings", COMPANY)
		settings.append("prepayments", {"year": 2027, "dauerfristverlaengerung": 1})
		settings.save()
		draft = frappe.get_doc({"doctype": "VAT Return Extension", "company": COMPANY, "year": 2027}).insert()
		sondervorauszahlung = (SVZ, "2027", date(2027, 2, 10), 82)
		self.assertIn((*sondervorauszahlung, "Offen"), self.deadlines(horizon=90))
		for status in ("Erfolgreich", "Unbekannt"):
			with self.subTest(status=status):
				frappe.db.delete("ELSTER Transmission", {"document": draft.name})
				draft.new_transmission("send", simulated=False, status=status)
				self.assertIn((*sondervorauszahlung, "Abgegeben"), self.deadlines(horizon=90))
		frappe.db.set_value("VAT Return Extension", draft.name, "docstatus", 2)
		self.assertIn((*sondervorauszahlung, "Abgegeben"), self.deadlines(horizon=90))

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


# Keeps its annual filings in Steuerbote since 4 January 2027, has no VAT Return Settings and no Steuerberatung, and
# its settings hold no size class.
ANNUAL_COMPANY = "Steuerbote Test Jahresfristen GmbH"
# A Tuesday. 31 July 2027 is a Saturday, so the Erklärungen of 2026 are due on Monday, 2 August 2027.
SUMMER = "2027-07-20 09:00:00"
ERKLAERUNGEN = date(2027, 8, 2)
UST, KST, GEWST, EBILANZ, FESTSTELLUNG, OFFENLEGUNG = (kind.value for kind in annual.KINDS)
WITH_KST = "No deadline of its own: with the Körperschaftsteuererklärung"
NO_SIZE_CLASS = "No size class for the fiscal year: eight months (§ 42a Abs. 2 GmbHG)"


def link(doctype: str, name: str) -> str:
	return f'<a href="/desk/{doctype.lower().replace(" ", "-")}/{name}">{name}</a>'


class TestOffeneFristenAnnual(IntegrationTestCase):
	"""The annual deadlines in the report, from the test DocTypes in place of those of the annual filings."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		annual_deadlines.install()
		make_annual_company(ANNUAL_COMPANY, "STFJ", "2027-01-04 08:00:00")

	def setUp(self):
		frappe.db.savepoint("offene_fristen_annual_test")
		self.addCleanup(frappe.db.rollback, save_point="offene_fristen_annual_test")
		self.enterContext(annual_deadlines.use_test_doctypes())

	def report(self, today: str = SUMMER, **filters) -> tuple[list[dict], list[dict]]:
		with self.freeze_time(today):
			return execute({"company": ANNUAL_COMPANY, "horizon": 180, **filters})

	def rows(self, today: str = SUMMER, **filters) -> list[dict]:
		return self.report(today, **filters)[1]

	def deadlines(self, today: str = SUMMER, **filters) -> list[tuple]:
		return [
			(row["kind"], row["period_label"], row["due"], row["days"], row["status"], row["note"])
			for row in self.rows(today, **filters)
		]

	def row(self, kind: str, period_label: str = "2026") -> dict:
		(found,) = [row for row in self.rows() if (row["kind"], row["period_label"]) == (kind, period_label)]
		return found

	def state(self, kind: str, period_label: str = "2026") -> tuple[str, str, str]:
		found = self.row(kind, period_label)
		return found["status"], found["document"], found["document_status"]

	def change_settings(self, **tables) -> None:
		settings = frappe.get_doc("Annual Filing Settings", ANNUAL_COMPANY)
		for table, rows in tables.items():
			settings.set(table, rows)
		settings.save()

	def test_lists_the_annual_deadlines_of_the_annual_filing_settings_by_due_date(self):
		self.assertEqual(
			self.deadlines(),
			[
				(UST, "2026", ERKLAERUNGEN, 13, "Fehlt", ""),
				(KST, "2026", ERKLAERUNGEN, 13, "Fehlt", ""),
				(GEWST, "2026", ERKLAERUNGEN, 13, "Fehlt", ""),
				(EBILANZ, "2026", ERKLAERUNGEN, 13, "Fehlt", WITH_KST),
				(FESTSTELLUNG, "2026", date(2027, 8, 31), 42, "Fehlt", NO_SIZE_CLASS),
				(OFFENLEGUNG, "2026", date(2027, 12, 31), 164, "Fehlt", ""),
			],
		)
		self.assertEqual({row["company"] for row in self.rows()}, {ANNUAL_COMPANY})

	def test_lists_a_company_without_vat_return_settings_among_all(self):
		self.assertFalse(frappe.db.exists("VAT Return Settings", ANNUAL_COMPANY))
		self.assertIn(ANNUAL_COMPANY, {row["company"] for row in self.rows(company=None)})

	def test_a_missing_annual_document_links_a_new_one_of_its_year(self):
		self.assertEqual(
			self.row(KST)["document"],
			'<a href="/desk/steuerbote-test-annual-filing/new?company=Steuerbote+Test+Jahresfristen+GmbH'
			'&amp;year=2026">Create Document</a>',
		)
		self.assertEqual(self.row(OFFENLEGUNG)["document_status"], "")

	def test_a_draft_keeps_its_annual_deadline_open_with_its_status(self):
		draft = insert_annual(FILING_DOCTYPE, ANNUAL_COMPANY, "Berechnet")
		self.assertEqual(self.state(KST), ("Offen", link(FILING_DOCTYPE, draft), "Berechnet"))

	def test_a_filed_erklaerung_files_its_deadline(self):
		filed = insert_annual(
			FILING_DOCTYPE, ANNUAL_COMPANY, "Abgegeben", 1, filed_via="mein_elster", filed_on="2027-07-15"
		)
		self.assertEqual(self.state(GEWST), ("Abgegeben", link(FILING_DOCTYPE, filed), "Abgegeben"))

	def test_a_draft_sent_through_steuerbote_files_its_deadline(self):
		"""ELSTER accepted it, or the outcome of its Senden is unknown, while it stayed a draft: the Finanzamt has it,
		or may have it."""
		draft = insert_annual(FILING_DOCTYPE, ANNUAL_COMPANY, "Bereit")
		insert_transmission(FILING_DOCTYPE, draft, "Fehlgeschlagen", "2027-07-19 10:00:00")
		self.assertEqual(self.state(KST), ("Offen", link(FILING_DOCTYPE, draft), "Bereit"))
		for status in ("Erfolgreich", "Unbekannt"):
			with self.subTest(status=status):
				sent = insert_transmission(FILING_DOCTYPE, draft, status, "2027-07-19 11:00:00")
				self.assertEqual(self.state(KST), ("Abgegeben", link(FILING_DOCTYPE, draft), "Bereit"))
				frappe.db.delete("ELSTER Transmission", {"name": sent})

	def test_the_jahresabschluss_files_its_feststellung_and_then_its_offenlegung(self):
		accounts = insert_annual(ACCOUNTS_DOCTYPE, ANNUAL_COMPANY, "Festgestellt", 1)
		self.assertEqual(
			self.state(FESTSTELLUNG), ("Abgegeben", link(ACCOUNTS_DOCTYPE, accounts), "Festgestellt")
		)
		self.assertEqual(self.state(OFFENLEGUNG), ("Offen", link(ACCOUNTS_DOCTYPE, accounts), "Festgestellt"))
		frappe.db.set_value(
			ACCOUNTS_DOCTYPE,
			accounts,
			{"status": "Übermittelt", "filed_via": "upload", "filed_on": "2027-07-16"},
		)
		self.assertEqual(
			self.state(OFFENLEGUNG), ("Abgegeben", link(ACCOUNTS_DOCTYPE, accounts), "Übermittelt")
		)

	def test_a_jahresabschluss_changed_after_its_upload_keeps_the_offenlegung_and_awaits_its_feststellung(
		self,
	):
		uploaded = insert_annual(
			ACCOUNTS_DOCTYPE, ANNUAL_COMPANY, "Ersetzt", 2, filed_via="upload", filed_on="2027-07-16"
		)
		amendment = insert_annual(ACCOUNTS_DOCTYPE, ANNUAL_COMPANY, "Berechnet", amended_from=uploaded)
		self.assertEqual(self.state(OFFENLEGUNG), ("Abgegeben", link(ACCOUNTS_DOCTYPE, uploaded), "Ersetzt"))
		self.assertEqual(self.state(FESTSTELLUNG), ("Offen", link(ACCOUNTS_DOCTYPE, amendment), "Berechnet"))

	def test_the_annual_filing_settings_set_the_days(self):
		self.change_settings(
			years=[
				{
					"year": 2026,
					"advisor_prepares": 1,
					"kleinunternehmer": 1,
					"exempt_264_3": 1,
					"exempt_264_3_reason": "Konzernabschluss der Muttergesellschaft",
				}
			],
			size_history=[
				{"fiscal_year_end": "2026-12-31", "size_class": "Klein", "source": "Jahresabschluss 2026"}
			],
		)
		self.assertEqual(
			self.deadlines(horizon=240),
			[
				(FESTSTELLUNG, "2026", date(2027, 11, 30), 133, "Fehlt", ""),
				(
					KST,
					"2026",
					date(2028, 2, 29),
					224,
					"Fehlt",
					"Prepared by a Steuerberatung (§ 149 Abs. 3 AO)",
				),
				(
					GEWST,
					"2026",
					date(2028, 2, 29),
					224,
					"Fehlt",
					"Prepared by a Steuerberatung (§ 149 Abs. 3 AO)",
				),
				(
					EBILANZ,
					"2026",
					date(2028, 2, 29),
					224,
					"Fehlt",
					f"{WITH_KST}; Prepared by a Steuerberatung (§ 149 Abs. 3 AO)",
				),
			],
		)

	def test_an_early_order_of_the_finanzamt_holds_for_every_erklaerung_of_the_year(self):
		self.change_settings(years=[{"year": 2026, "advisor_prepares": 1, "early_request_kst": "2027-09-15"}])
		early = "Ordered early by the Finanzamt (§ 149 Abs. 4 AO)"
		self.assertEqual(
			[row[:3] + row[5:] for row in self.deadlines() if row[0] in (UST, KST, GEWST, EBILANZ)],
			[
				(UST, "2026", date(2027, 9, 15), early),
				(KST, "2026", date(2027, 9, 15), early),
				(GEWST, "2026", date(2027, 9, 15), early),
				(EBILANZ, "2026", date(2027, 9, 15), f"{WITH_KST}; {early}"),
			],
		)

	def test_a_holiday_of_the_company_moves_the_erklaerungen(self):
		holidays = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": "Steuerbote Test Jahresfristen 2027",
				"from_date": "2027-01-01",
				"to_date": "2027-12-31",
				"holidays": [{"holiday_date": "2027-08-02", "description": "Testtag"}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Company", ANNUAL_COMPANY, "default_holiday_list", holidays.name)
		self.assertEqual(self.row(KST)["due"], date(2027, 8, 3))
		self.assertEqual(
			annual_deadline(ANNUAL_COMPANY, Kind.KOERPERSCHAFTSTEUERERKLAERUNG, 2026), date(2027, 8, 3)
		)

	def test_the_founding_year_lists_the_eroeffnungsbilanz_beside_the_e_bilanz(self):
		frappe.db.set_value("Company", ANNUAL_COMPANY, "date_of_establishment", "2026-03-02")
		self.assertEqual(
			self.row(EBILANZ, "Eröffnungsbilanz 2026")["document"],
			'<a href="/desk/steuerbote-test-electronic-balance-sheet/new?company=Steuerbote+Test+Jahresfristen+GmbH'
			'&amp;year=2026&amp;statement_type=Er%C3%B6ffnungsbilanz">Create Document</a>',
		)
		opening = insert_annual(
			BALANCE_SHEET, ANNUAL_COMPANY, "Abgegeben", 1, statement_type="Eröffnungsbilanz"
		)
		self.assertEqual(
			self.state(EBILANZ, "Eröffnungsbilanz 2026"),
			("Abgegeben", link(BALANCE_SHEET, opening), "Abgegeben"),
		)
		self.assertEqual(self.state(EBILANZ)[0], "Fehlt")
		self.assertEqual(
			annual_deadline(ANNUAL_COMPANY, Kind.E_BILANZ, 2026, opening_balance=True), ERKLAERUNGEN
		)

	def test_an_e_bilanz_of_the_jahresabschluss_files_only_its_year(self):
		balance_sheet = insert_annual(
			BALANCE_SHEET, ANNUAL_COMPANY, "Abgegeben", 1, statement_type="Jahresabschluss"
		)
		self.assertEqual(self.state(EBILANZ), ("Abgegeben", link(BALANCE_SHEET, balance_sheet), "Abgegeben"))
		self.assertEqual([row["period_label"] for row in self.rows() if row["kind"] == EBILANZ], ["2026"])

	def test_a_kind_whose_doctype_the_site_lacks_stays_out(self):
		missing = "Steuerbote Test Missing Annual Return"
		doctypes = MappingProxyType(
			{
				missing: AnnualDocType((Kind.UMSATZSTEUERERKLAERUNG,)),
				FILING_DOCTYPE: AnnualDocType((Kind.KOERPERSCHAFTSTEUERERKLAERUNG,)),
			}
		)
		self.assertFalse(frappe.db.exists("DocType", missing))
		with (
			patch.object(annual, "DOCTYPES", doctypes),
			patch.object(annual, "AWAITING_DOCTYPES", (missing,)),
		):
			self.assertEqual([row["kind"] for row in self.rows()], [KST])

	def test_an_overdue_deadline_from_before_the_annual_filing_settings_is_left_out(self):
		autumn = "2027-09-01 09:00:00"
		self.assertIn(KST, [row["kind"] for row in self.rows(autumn)])
		frappe.db.set_value(
			"Annual Filing Settings", ANNUAL_COMPANY, "creation", "2027-08-03 08:00:00", update_modified=False
		)
		self.assertEqual([row["kind"] for row in self.rows(autumn)], [FESTSTELLUNG, OFFENLEGUNG])
		draft = insert_annual(FILING_DOCTYPE, ANNUAL_COMPANY, "Entwurf")
		kst = [row for row in self.rows(autumn) if row["kind"] == KST]
		self.assertEqual(
			[(row["status"], row["days"], row["document"]) for row in kst],
			[("Offen", -30, link(FILING_DOCTYPE, draft))],
		)

	def test_the_due_date_of_an_annual_document_is_that_of_the_report(self):
		self.assertEqual(annual_deadline(ANNUAL_COMPANY, Kind.UMSATZSTEUERERKLAERUNG, 2026), ERKLAERUNGEN)
		self.assertEqual(annual_deadline(ANNUAL_COMPANY, Kind.OFFENLEGUNG, 2026), date(2027, 12, 31))
		self.assertIsNone(annual_deadline(ANNUAL_COMPANY, Kind.UMSATZSTEUERERKLAERUNG, 2025))
		self.assertIsNone(
			annual_deadline("Steuerbote Test Fristenbericht ohne Einstellungen GmbH", Kind.OFFENLEGUNG, 2026)
		)
