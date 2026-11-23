"""The daily reminder of the deadlines on a site: one e-mail per company and day with the deadlines not filed and
links to their documents, a Deadline Reminder for each, never twice for a deadline on one day, nothing without
recipients, and records that nobody changes; with Annual Filing Settings also the annual deadlines, with their
notes, for every company whose VAT Return Settings name recipients."""

from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.steuerbote import deadlines
from steuerbote.steuerbote.doctype.deadline_reminder.deadline_reminder import reminder_name
from steuerbote.tests import annual_deadlines
from steuerbote.tests.annual_deadlines import FILING_DOCTYPE, insert_annual, make_annual_company
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_mapping,
	make_settings,
	post_journal_entry,
)

# The companies and their accounts are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company"]

DOCTYPE = "Deadline Reminder"
SETTINGS = "VAT Return Settings"
# Files the Voranmeldung and the Zusammenfassende Meldung monthly from 2026, without the Dauerfristverlängerung,
# keeps its filings in Steuerbote since 1 November 2026 and delivered goods to another member state in October.
COMPANY = "Steuerbote Test Fristerinnerung GmbH"
# The same, but its settings name no one to remind.
SILENT_COMPANY = "Steuerbote Test Fristen ohne Empfänger GmbH"
RECIPIENTS = "buchhaltung@example.com\nsteuerberatung@example.com"
# A Friday: the Voranmeldung for October was due on 10 November, the Zusammenfassende Meldung for October is due on
# 25 November, the Voranmeldung for November on 10 December.
TODAY = "2026-11-20 06:00:00"
ACCOUNTS = {
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
}


def make_monthly_company(company: str, abbr: str, recipients: str) -> None:
	make_company(company, abbr)
	accounts = {
		number: make_account(company, number, name, root_type)
		for number, (name, root_type) in ACCOUNTS.items()
	}
	make_settings(
		company,
		[(2026, "monthly", 1)],
		zm_rules=[{"year": 2026, "valid_from_month": 1, "rhythm": "monthly"}],
		deadline_recipients=recipients,
		reminder_days=7,
	)
	frappe.db.set_value(SETTINGS, company, "creation", "2026-11-01 08:00:00", update_modified=False)
	make_mapping(company)
	post_journal_entry(company, "2026-10-15", [(accounts["1400"], 1000, 0), (accounts["8125"], 0, 1000)])


def filed_vat_return(company: str, month: int):
	doc = frappe.get_doc(
		{
			"doctype": "VAT Return",
			"company": company,
			"year": 2026,
			"rhythm": "monthly",
			"period_index": month,
			"remarks": "Testabgabe",
		}
	).insert()
	doc.calculate()
	doc.reload()
	doc.mark_filed_outside("In Mein ELSTER abgegeben")
	return doc


class TestDeadlineReminder(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_monthly_company(COMPANY, "STFE", RECIPIENTS)
		make_monthly_company(SILENT_COMPANY, "STFO", "")

	def setUp(self):
		frappe.db.savepoint("deadline_reminder_test")
		self.addCleanup(frappe.db.rollback, save_point="deadline_reminder_test")

	def send(self, day: str = TODAY):
		"""One run of the daily job on the day, with the e-mails it would send."""
		with self.freeze_time(day), patch.object(frappe, "sendmail") as sendmail:
			deadlines.send_reminders()
		return sendmail

	def error_logs(self, company: str) -> set[str]:
		"""The Error Logs of the company. Frappe keeps them in a table outside the transaction, so they stay when a
		test rolls back."""
		return set(
			frappe.get_all(
				"Error Log", filters={"reference_doctype": SETTINGS, "reference_name": company}, pluck="name"
			)
		)

	def reminders(self, company: str = COMPANY) -> list[tuple]:
		return [
			(row.kind, row.period_label, row.due_date, row.sent_on)
			for row in frappe.get_all(
				DOCTYPE,
				filters={"company": company},
				fields=["kind", "period_label", "due_date", "sent_on"],
				order_by="sent_on, due_date",
			)
		]

	def test_sends_the_recipients_one_e_mail_with_the_deadlines_not_filed(self):
		sendmail = self.send()
		sendmail.assert_called_once()
		mail = sendmail.call_args.kwargs
		self.assertEqual(mail["recipients"], ["buchhaltung@example.com", "steuerberatung@example.com"])
		self.assertEqual(mail["subject"], f"Steuerbote: offene Fristen für {COMPANY}")
		self.assertEqual((mail["reference_doctype"], mail["reference_name"]), (SETTINGS, COMPANY))
		message = mail["message"]
		self.assertIn(f"Diese Fristen für {COMPANY} sind noch nicht abgegeben:", message)
		self.assertIn(
			"<td>Umsatzsteuer-Voranmeldung</td><td>Oktober 2026</td><td>10.11.2026</td><td>-10</td><td>Fehlt</td>",
			message,
		)
		self.assertIn(
			"<td>Zusammenfassende Meldung</td><td>Oktober 2026</td><td>25.11.2026</td><td>5</td><td>Fehlt</td>",
			message,
		)
		self.assertNotIn("November 2026", message)
		self.assertIn(
			"<th>Art</th><th>Zeitraum</th><th>Fällig am</th><th>Tage</th><th>Status</th><th>Beleg</th>",
			message,
		)
		self.assertIn(
			"/desk/vat-return/new?company=Steuerbote+Test+Fristerinnerung+GmbH&amp;year=2026&amp;rhythm=monthly"
			'&amp;period_index=10">Erstellen</a>',
			message,
		)
		self.assertIn("/desk/query-report/Offene%20Fristen", message)
		self.assertEqual(
			self.reminders(),
			[
				("Umsatzsteuer-Voranmeldung", "Oktober 2026", date(2026, 11, 10), date(2026, 11, 20)),
				("Zusammenfassende Meldung", "Oktober 2026", date(2026, 11, 25), date(2026, 11, 20)),
			],
		)

	def test_leaves_out_what_is_filed_and_links_what_is_open(self):
		filed_vat_return(COMPANY, 10)
		statement = frappe.get_doc(
			{
				"doctype": "Recapitulative Statement",
				"company": COMPANY,
				"year": 2026,
				"period_kind": "month",
				"period_index": 10,
			}
		).insert()
		message = self.send().call_args.kwargs["message"]
		self.assertNotIn("<td>Umsatzsteuer-Voranmeldung</td>", message)
		self.assertIn("<td>5</td><td>Offen</td>", message)
		self.assertIn(f'/desk/recapitulative-statement/{statement.name}">{statement.name}</a>', message)
		self.assertEqual(
			self.reminders(),
			[("Zusammenfassende Meldung", "Oktober 2026", date(2026, 11, 25), date(2026, 11, 20))],
		)

	def test_reminds_no_deadline_twice_on_one_day_and_again_the_next(self):
		self.assertEqual(self.send().call_count, 1)
		self.assertEqual(self.send().call_count, 0)
		self.assertEqual(len(self.reminders()), 2)
		self.assertEqual(self.send("2026-11-21 06:00:00").call_count, 1)
		self.assertEqual(len(self.reminders()), 4)

	def test_a_deadline_not_reminded_today_goes_out_the_same_day(self):
		self.send()
		frappe.db.set_value(SETTINGS, COMPANY, "reminder_days", 20)
		sendmail = self.send()
		sendmail.assert_called_once()
		message = sendmail.call_args.kwargs["message"]
		self.assertIn("<td>Umsatzsteuer-Voranmeldung</td><td>November 2026</td><td>10.12.2026</td>", message)
		self.assertNotIn("Oktober 2026", message)

	def test_sends_nothing_without_recipients(self):
		logged = self.error_logs(SILENT_COMPANY)
		sendmail = self.send()
		self.assertEqual([call.kwargs["reference_name"] for call in sendmail.call_args_list], [COMPANY])
		self.assertEqual(self.reminders(SILENT_COMPANY), [])
		self.assertEqual(self.error_logs(SILENT_COMPANY), logged)
		with patch.object(frappe, "sendmail") as sendmail:
			self.assertFalse(deadlines.remind(SILENT_COMPANY, date(2026, 11, 20)))
		sendmail.assert_not_called()

	def test_an_entry_that_is_no_address_gets_no_reminder(self):
		entries = "buchhaltung@example.com\nkeine Adresse\n\n steuerberatung@example.com "
		logged = self.error_logs(COMPANY)
		self.assertEqual(
			deadlines.recipients_of(COMPANY, entries),
			["buchhaltung@example.com", "steuerberatung@example.com"],
		)
		(log,) = self.error_logs(COMPANY) - logged
		self.assertIn("keine Adresse", frappe.db.get_value("Error Log", log, "error"))

	def test_a_company_whose_reminder_fails_leaves_the_others(self):
		frappe.db.set_value(SETTINGS, SILENT_COMPANY, "deadline_recipients", RECIPIENTS)
		original = deadlines.remind

		def remind(company, today):
			if company == SILENT_COMPANY:
				raise RuntimeError("Testfehler")
			return original(company, today)

		logged = self.error_logs(SILENT_COMPANY)
		with patch.object(deadlines, "remind", remind):
			sendmail = self.send()
		self.assertEqual([call.kwargs["reference_name"] for call in sendmail.call_args_list], [COMPANY])
		self.assertEqual(len(self.reminders()), 2)
		(log,) = self.error_logs(SILENT_COMPANY) - logged
		self.assertIn("Testfehler", frappe.db.get_value("Error Log", log, "error"))

	def test_a_reminder_is_recorded_once_for_a_deadline_and_a_day(self):
		values = {
			"doctype": DOCTYPE,
			"company": COMPANY,
			"kind": "Sondervorauszahlung",
			"period_label": "2027",
			"due_date": "2027-02-10",
			"sent_on": "2027-02-01",
		}
		first = frappe.get_doc(values).insert(ignore_permissions=True)
		self.assertEqual(
			first.name, reminder_name(COMPANY, "Sondervorauszahlung", "2027", "2027-02-10", "2027-02-01")
		)
		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(values).insert(ignore_permissions=True)
		first.period_label = "2028"
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be changed"):
			first.save(ignore_permissions=True)


# Files no Voranmeldung, keeps its annual filings in Steuerbote since 4 January 2027 and has no Steuerberatung; its
# VAT Return Settings name the recipients and fourteen days of notice.
ANNUAL_COMPANY = "Steuerbote Test Jahreserinnerung GmbH"
# Has Annual Filing Settings, but no VAT Return Settings, and so nobody to remind.
ANNUAL_ONLY = "Steuerbote Test Jahreserinnerung ohne UStVA GmbH"
# A Tuesday: the Erklärungen of 2026 are due on Monday, 2 August 2027, in 13 days.
SUMMER = "2027-07-20 06:00:00"
ERKLAERUNGEN = date(2027, 8, 2)


class TestAnnualDeadlineReminder(IntegrationTestCase):
	"""The annual deadlines in the reminder, from the test DocTypes in place of those of the annual filings."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		annual_deadlines.install()
		make_annual_company(ANNUAL_COMPANY, "STFA", "2027-01-04 08:00:00")
		make_settings(ANNUAL_COMPANY, [(2026, "none", 1)], deadline_recipients=RECIPIENTS, reminder_days=14)
		make_annual_company(ANNUAL_ONLY, "STFU", "2027-01-04 08:00:00")

	def setUp(self):
		frappe.db.savepoint("annual_deadline_reminder_test")
		self.addCleanup(frappe.db.rollback, save_point="annual_deadline_reminder_test")
		self.enterContext(annual_deadlines.use_test_doctypes())

	def send(self, day: str = SUMMER):
		with self.freeze_time(day), patch.object(frappe, "sendmail") as sendmail:
			deadlines.send_reminders()
		return sendmail

	def error_logs(self, company: str) -> set[str]:
		return set(frappe.get_all("Error Log", filters={"reference_name": company}, pluck="name"))

	def mail_to(self, sendmail, company: str) -> dict | None:
		found = [call.kwargs for call in sendmail.call_args_list if call.kwargs["reference_name"] == company]
		return found[0] if found else None

	def reminders(self, company: str = ANNUAL_COMPANY) -> set[tuple]:
		return {
			(row.kind, row.period_label, row.due_date, row.sent_on)
			for row in frappe.get_all(
				"Deadline Reminder",
				filters={"company": company},
				fields=["kind", "period_label", "due_date", "sent_on"],
			)
		}

	def test_reminds_of_the_annual_deadlines_with_their_notes(self):
		mail = self.mail_to(self.send(), ANNUAL_COMPANY)
		message = mail["message"]
		self.assertIn(
			"<th>Art</th><th>Zeitraum</th><th>Fällig am</th><th>Tage</th><th>Status</th><th>Beleg</th>"
			"<th>Stand des Belegs</th><th>Hinweis</th>",
			message,
		)
		for kind in ("Umsatzsteuererklärung", "Körperschaftsteuererklärung", "Gewerbesteuererklärung"):
			with self.subTest(kind=kind):
				self.assertIn(
					f"<td>{kind}</td><td>2026</td><td>02.08.2027</td><td>13</td><td>Fehlt</td>", message
				)
		self.assertIn("<td></td><td>Keine eigene Frist: mit der Körperschaftsteuererklärung</td>", message)
		self.assertIn(
			"/desk/steuerbote-test-annual-filing/new?company=Steuerbote+Test+Jahreserinnerung+GmbH&amp;year=2026"
			'">Erstellen</a>',
			message,
		)
		self.assertNotIn("Feststellung Jahresabschluss", message)
		self.assertEqual(
			self.reminders(),
			{
				(kind, "2026", ERKLAERUNGEN, date(2027, 7, 20))
				for kind in (
					"Umsatzsteuererklärung",
					"Körperschaftsteuererklärung",
					"Gewerbesteuererklärung",
					"E-Bilanz",
				)
			},
		)

	def test_leaves_out_what_is_filed(self):
		insert_annual(
			FILING_DOCTYPE, ANNUAL_COMPANY, "Abgegeben", 1, filed_via="other_way", filed_on="2027-07-15"
		)
		message = self.mail_to(self.send(), ANNUAL_COMPANY)["message"]
		self.assertNotIn("<td>Körperschaftsteuererklärung</td>", message)
		self.assertIn("<td>E-Bilanz</td><td>2026</td><td>02.08.2027</td><td>13</td><td>Fehlt</td>", message)
		self.assertEqual({row[0] for row in self.reminders()}, {"E-Bilanz"})

	def test_names_the_state_of_the_document_of_an_open_deadline(self):
		draft = insert_annual(FILING_DOCTYPE, ANNUAL_COMPANY, "Berechnet")
		message = self.mail_to(self.send(), ANNUAL_COMPANY)["message"]
		self.assertIn(
			f'/desk/steuerbote-test-annual-filing/{draft}">{draft}</a></td><td>Berechnet</td><td></td>',
			message,
		)

	def test_a_company_without_vat_return_settings_has_nobody_to_remind(self):
		logged = self.error_logs(ANNUAL_ONLY)
		self.assertIsNone(self.mail_to(self.send(), ANNUAL_ONLY))
		self.assertEqual(self.reminders(ANNUAL_ONLY), set())
		self.assertEqual(self.error_logs(ANNUAL_ONLY), logged)
		with patch.object(frappe, "sendmail") as sendmail:
			self.assertFalse(deadlines.remind(ANNUAL_ONLY, date(2027, 7, 20)))
		sendmail.assert_not_called()

	def test_the_job_asks_every_company_with_vat_return_or_annual_filing_settings(self):
		asked = []
		with patch.object(deadlines, "remind", lambda company, today: asked.append(company)):
			self.send()
		self.assertIn(ANNUAL_COMPANY, asked)
		self.assertIn(ANNUAL_ONLY, asked)
		self.assertEqual(asked, sorted(set(asked)))
