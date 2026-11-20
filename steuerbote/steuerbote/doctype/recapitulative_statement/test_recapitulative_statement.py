"""Berechnen, USt-IdNrn. prüfen, the CSV file for Mein ELSTER, overrides, the Berichtigung and the filing marks of
the Zusammenfassende Meldung, against invoices and payments written as ERPNext keeps them.

The confirmation runs through the real core of steuerbote.vatid; FakeBzst stands in for the transport and
answers as the eVatR API of the BZSt does, so no test reaches the network.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today
from frappe.utils.data import convert_utc_to_system_timezone

from steuerbote.steuerbote.doctype.recapitulative_statement import recapitulative_statement as controller
from steuerbote.steuerbote.doctype.recapitulative_statement.recapitulative_statement import run_confirmation
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_customer,
	make_mapping,
	make_settings,
	post_payment_entry,
	post_sales_invoice,
)
from steuerbote.vatid.tests.fakes import BZST_ID, START, FakeClock, bzst

# The companies, their accounts, customers and vouchers are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Account",
	"Address",
	"Company",
	"Customer",
	"DocType",
	"User",
	"VAT ID Confirmation",
]

DOCTYPE = "Recapitulative Statement"
# Files the ZM monthly from January 2026, the sonstige Leistungen in their own month, with a holiday list
# that has the Pfingstmontag.
COMPANY = "Steuerbote Test Zusammenfassende Meldung GmbH"
# Files the ZM quarterly from January 2026 and delivers for 60,000 euros in January.
QUARTERLY_COMPANY = "Steuerbote Test ZM Schwelle GmbH"
# Files like COMPANY and confirms the USt-IdNrn. of its customers, which are kept per company.
CONFIRMING_COMPANY = "Steuerbote Test USt-IdNr.-Prüfung GmbH"
# The example numbers of the OpenAPI document of the eVatR API and an invented French number.
OWN_VAT_ID = "DE123456789"
AUSTRIAN = "ATU12345678"
FRENCH = "FR12345678901"
ALPEN = "Alpen Handel GmbH (ZM)"
PARIS = "Paris Services SA (ZM)"
# The form of TransferTicketSType in headerbasis_datentypen.xsd, invented.
TICKET = "ab123cdefghijkmnopqrstuvwxyz0123"
HEADER = b"#v3.0\n#ve3.2.1\nUmsatzsteuer-Identifikationsnummer (USt-IdNr.),Summe (Euro),Art der Leistung\n"

# SKR03: intra-community deliveries, their Skonti, Dreiecksgeschäfte, EU services, receivables and a bank.
ACCOUNTS = {
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"8743": ("Gewährte Skonti innergemeinschaftliche Lieferungen", "Income"),
	"8130": ("Lieferungen des ersten Abnehmers bei Dreiecksgeschäften", "Income"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1200": ("Bank", "Asset"),
}


def money(value) -> Decimal:
	return Decimal(str(value)).quantize(Decimal("0.01"))


def contents(url: str) -> bytes:
	return Path(frappe.get_doc("File", {"file_url": url}).get_full_path()).read_bytes()


def answer(status: str = "evatr-0000", http: int = 200, **fields):
	return bzst(status, http, **fields)


class FakeBzst:
	"""Stands in for the transport of a confirmation: answers each query with the next answer for its number,
	as the eVatR API would, and keeps the queries."""

	def __init__(self, answers: dict[str, list]):
		self.answers = {number: list(queue) for number, queue in answers.items()}
		self.requests: list[dict] = []

	def __call__(self, request):
		query = json.loads(request.body)
		self.requests.append(query)
		return self.answers[query["angefragteUstid"]].pop(0)


class TestRecapitulativeStatement(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.account = cls.make_monthly_company(COMPANY, "STZM")
		cls.confirming_account = cls.make_monthly_company(CONFIRMING_COMPANY, "STZP")
		holidays = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": "Steuerbote Test Feiertage 2026",
				"from_date": "2026-01-01",
				"to_date": "2026-12-31",
				"holidays": [{"holiday_date": "2026-05-25", "description": "Pfingstmontag"}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Company", COMPANY, "default_holiday_list", holidays.name)
		cls.alpen_address = make_customer(ALPEN, "Austria", AUSTRIAN, city="Wien")
		cls.paris_address = make_customer(PARIS, "France", FRENCH, city="Paris", primary=False)
		for month in (3, 4, 7, 8):
			cls.post_month(COMPANY, "STZM", cls.account, month)
		for month in (5, 6):
			cls.post_month(CONFIRMING_COMPANY, "STZP", cls.confirming_account, month)

		make_company(QUARTERLY_COMPANY, "STZQ")
		quarterly = {
			number: make_account(QUARTERLY_COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(
			QUARTERLY_COMPANY,
			[(2026, "monthly", 1)],
			ust_idnr=OWN_VAT_ID,
			zm_rules=[{"year": 2026, "valid_from_month": 1, "rhythm": "quarterly"}],
		)
		make_mapping(QUARTERLY_COMPANY)
		post_sales_invoice(
			QUARTERLY_COMPANY,
			"SINV-STZQ-01-1",
			ALPEN,
			"2026-01-15",
			[(quarterly["1400"], 60000, 0), (quarterly["8125"], 0, 60000)],
		)

	@classmethod
	def make_monthly_company(cls, company: str, abbr: str) -> dict[str, str]:
		"""A company that files the ZM monthly from January 2026, the sonstige Leistungen in their own month."""
		make_company(company, abbr)
		account = {
			number: make_account(company, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(
			company,
			[(2026, "monthly", 1)],
			ust_idnr=OWN_VAT_ID,
			zm_rules=[{"year": 2026, "valid_from_month": 1, "rhythm": "monthly", "services_monthly": 1}],
		)
		make_mapping(company)
		return account

	@classmethod
	def post_month(cls, company: str, abbr: str, account: dict[str, str], month: int) -> None:
		"""An intra-community delivery to Alpen paid with a Skonto of 200 euros and a service to Paris."""
		a = account
		day = f"2026-{month:02d}-10"
		invoice = post_sales_invoice(
			company,
			f"SINV-{abbr}-{month:02d}-1",
			ALPEN,
			day,
			[(a["1400"], 10000, 0), (a["8125"], 0, 10000)],
			customer_address=cls.alpen_address,
		)
		post_sales_invoice(
			company,
			f"SINV-{abbr}-{month:02d}-2",
			PARIS,
			day,
			[(a["1400"], 3000, 0), (a["8336"], 0, 3000)],
			customer_address=cls.paris_address,
		)
		post_payment_entry(
			company,
			f"PE-{abbr}-{month:02d}-1",
			ALPEN,
			f"2026-{month:02d}-20",
			[invoice],
			[(a["1200"], 9800, 0), (a["8743"], 200, 0), (a["1400"], 0, 10000)],
		)

	def statement(self, index: int, company: str = COMPANY, kind: str = "month", **fields):
		return frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"company": company,
				"year": 2026,
				"period_kind": kind,
				"period_index": index,
				**fields,
			}
		).insert()

	def calculated(self, index: int, **fields):
		doc = self.statement(index, **fields)
		doc.calculate()
		doc.reload()
		return doc

	def line(self, doc, vat_id: str):
		return next(row for row in doc.lines if row.vat_id == vat_id)

	def confirm(self, doc, service: FakeBzst):
		"""USt-IdNrn. prüfen, with the job run at once against the fake transport."""
		with patch("frappe.enqueue") as enqueue:
			numbers = doc.confirm_vat_ids()
		(call,) = enqueue.call_args_list
		with (
			patch.object(controller, "UrllibFetch", lambda: service),
			patch.object(controller, "_clock", FakeClock()),
			patch("frappe.db.commit") as commit,
			patch("frappe.publish_realtime") as publish,
		):
			run_confirmation(name=call.kwargs["name"])
		doc.reload()
		return numbers, call, commit, publish

	def test_berechnen_makes_a_line_per_vat_id_and_art_from_two_invoices_and_a_skonto_payment(self):
		doc = self.calculated(3)
		self.assertEqual(
			(doc.period_label, doc.quart, str(doc.from_date), str(doc.to_date), str(doc.deadline)),
			("März 2026", 23, "2026-03-01", "2026-03-31", "2026-04-27"),
		)
		self.assertEqual(
			[
				(row.vat_id, row.art, row.party, money(row.amount), money(row.reported), row.in_file)
				for row in doc.lines
			],
			[
				(AUSTRIAN, "L", ALPEN, money(9800), money(9800), 1),
				(FRENCH, "S", PARIS, money(3000), money(3000), 1),
			],
		)
		self.assertEqual(
			[
				(row.voucher_type, row.voucher_no, row.kennzahl, money(row.amount), row.vat_id, row.customer)
				for row in doc.vouchers
			],
			[
				("Sales Invoice", "SINV-STZM-03-1", "41", money(10000), AUSTRIAN, ALPEN),
				("Payment Entry", "PE-STZM-03-1", "41", money(-200), AUSTRIAN, ALPEN),
				("Sales Invoice", "SINV-STZM-03-2", "21", money(3000), FRENCH, PARIS),
			],
		)
		self.assertEqual(
			(money(doc.total_l), money(doc.total_d), money(doc.total_s)), (money(9800), money(0), money(3000))
		)
		self.assertEqual(
			[
				(
					row.art,
					row.kennzahl,
					money(row.ledger),
					money(row.statement),
					row.balanced,
					row.filed_known,
				)
				for row in doc.reconciliation
			],
			[
				("L", "41", money(9800), money(9800), 1, 0),
				("D", "42", money(0), money(0), 1, 0),
				("S", "21", money(3000), money(3000), 1, 0),
			],
		)
		self.assertEqual((doc.status, doc.ready), ("Berechnet", 0))
		self.assertEqual(
			[(row.severity, row.code, row.party) for row in doc.hints],
			[
				("Fehler", "ZM-USTID-UNBESTAETIGT", ALPEN),
				("Fehler", "ZM-USTID-UNBESTAETIGT", PARIS),
				("Hinweis", "ZM-ABWEICHUNG-VORPERIODE", ""),
				("Hinweis", "ZM-ABWEICHUNG-VORPERIODE", ""),
			],
		)
		self.assertEqual(
			[
				(row.vat_id, row.art, money(row.current), money(row.previous), row.flagged)
				for row in doc.comparison
			],
			[(AUSTRIAN, "L", money(9800), money(0), 1), (FRENCH, "S", money(3000), money(0), 1)],
		)

	def test_the_lines_agree_with_the_voranmeldung_and_go_into_the_csv_file(self):
		vat_return = frappe.get_doc(
			{
				"doctype": "VAT Return",
				"company": COMPANY,
				"year": 2026,
				"rhythm": "monthly",
				"period_index": 4,
			}
		).insert()
		vat_return.calculate()
		vat_return.reload()
		vat_return.mark_filed_outside("In Mein ELSTER abgegeben")
		doc = self.calculated(4)
		self.assertEqual(doc.deadline, date(2026, 5, 26))
		self.assertEqual(
			[(row.art, money(row.reported), money(row.filed), row.filed_known) for row in doc.reconciliation],
			[
				("L", money(9800), money(9800), 1),
				("D", money(0), money(0), 1),
				("S", money(3000), money(3000), 1),
			],
		)
		self.assertNotIn("ZM-ABGLEICH-VORANMELDUNG", [row.code for row in doc.hints])
		self.assertNotIn("ZM-ABWEICHUNG-VORPERIODE", [row.code for row in doc.hints])
		with self.assertRaisesRegex(frappe.ValidationError, "The statement is not ready"):
			doc.make_csv_file()
		doc.remarks = "Beide USt-IdNrn. sind am 1. April 2026 qualifiziert bestätigt worden."
		doc.save()
		url = doc.make_csv_file()
		file = frappe.get_doc("File", {"file_url": url, "attached_to_name": doc.name})
		self.assertEqual(
			(file.attached_to_doctype, file.is_private, file.file_name), (DOCTYPE, 1, "ZM-2026-04.csv")
		)
		self.assertEqual(contents(url), HEADER + b"ATU12345678,9800,L\nFR12345678901,3000,S")
		self.assertEqual(doc.make_csv_file(), url)

	def test_ust_idnrn_pruefen_asks_the_bzst_and_keeps_every_answer(self):
		doc = self.calculated(5, company=CONFIRMING_COMPANY)
		qualified = {"ergFirmenname": "A", "ergStrasse": "A", "ergPlz": "A", "ergOrt": "A"}
		service = FakeBzst(
			{
				AUSTRIAN: [answer(), answer(**qualified)],
				FRENCH: [answer(), answer(**{**qualified, "ergStrasse": "D"})],
			}
		)
		numbers, call, commit, publish = self.confirm(doc, service)
		self.assertEqual(numbers, 2)
		self.assertEqual(call.args, (controller.CONFIRMATION_JOB,))
		self.assertEqual(
			{key: call.kwargs[key] for key in ("queue", "job_id", "enqueue_after_commit", "name")},
			{
				"queue": "long",
				"job_id": f"steuerbote:ustid:{doc.name}",
				"enqueue_after_commit": True,
				"name": doc.name,
			},
		)
		self.assertEqual(commit.call_count, 2)
		self.assertEqual(
			[
				(
					query["anfragendeUstid"],
					query["angefragteUstid"],
					query.get("firmenname"),
					query.get("ort"),
				)
				for query in service.requests
			],
			[
				(OWN_VAT_ID, AUSTRIAN, None, None),
				(OWN_VAT_ID, AUSTRIAN, ALPEN, "Wien"),
				(OWN_VAT_ID, FRENCH, None, None),
				(OWN_VAT_ID, FRENCH, PARIS, "Paris"),
			],
		)
		self.assertEqual((doc.status, doc.ready, doc.confirmation_in_progress), ("Bereit", 1, 0))
		self.assertNotIn("ZM-USTID-UNBESTAETIGT", [row.code for row in doc.hints])
		records = frappe.get_all(
			"VAT ID Confirmation",
			filters={"recapitulative_statement": doc.name},
			fields=[
				"name",
				"requested",
				"requester",
				"qualified",
				"previous",
				"result",
				"street_match",
				"requested_at",
			],
			order_by="creation asc",
		)
		self.assertEqual(
			[(record.requested, record.requester, record.qualified, record.result) for record in records],
			[
				(AUSTRIAN, OWN_VAT_ID, 0, "valid"),
				(AUSTRIAN, OWN_VAT_ID, 1, "valid"),
				(FRENCH, OWN_VAT_ID, 0, "valid"),
				(FRENCH, OWN_VAT_ID, 1, "valid"),
			],
		)
		self.assertEqual((records[1].previous, records[3].previous), (records[0].name, records[2].name))
		self.assertEqual(records[3].street_match, "D")
		self.assertEqual(records[0].requested_at, convert_utc_to_system_timezone(START).replace(tzinfo=None))
		self.assertEqual(
			[
				(
					row.vat_id,
					row.confirmation,
					row.confirmation_outcome,
					row.confirmation_service,
					row.consultation_id,
				)
				for row in doc.lines
			],
			[
				(AUSTRIAN, records[1].name, "valid", "bzst", BZST_ID),
				(FRENCH, records[3].name, "valid", "bzst", BZST_ID),
			],
		)
		self.assertEqual(doc.lines[0].confirmation_date, getdate(records[1].requested_at))
		answer_file = frappe.get_doc(
			"File", {"attached_to_doctype": "VAT ID Confirmation", "attached_to_name": records[0].name}
		)
		self.assertEqual((answer_file.is_private, answer_file.file_name), (1, f"{records[0].name}-bzst.json"))
		self.assertEqual(json.loads(contents(answer_file.file_url))["status"], "evatr-0000")
		(event,) = (call for call in publish.call_args_list if call.args[0] == controller.CONFIRMATION_EVENT)
		self.assertEqual(event.args[0], controller.CONFIRMATION_EVENT)
		self.assertEqual(event.args[1], {"statement": doc.name, "confirmed": 2, "failed": [], "error": None})

	def test_an_invalid_number_holds_the_statement_until_its_line_is_overridden_with_a_reason(self):
		doc = self.calculated(6, company=CONFIRMING_COMPANY)
		service = FakeBzst(
			{
				AUSTRIAN: [answer(), answer(ergFirmenname="A", ergStrasse="A", ergPlz="A", ergOrt="A")],
				FRENCH: [answer("evatr-2001", 404)],
			}
		)
		self.confirm(doc, service)
		self.assertEqual((doc.status, self.line(doc, FRENCH).blocked), ("Berechnet", 1))
		self.assertEqual(self.line(doc, FRENCH).confirmation_outcome, "invalid")
		self.assertIn(
			("Fehler", "ZM-USTID-UNGUELTIG", PARIS),
			[(row.severity, row.code, row.party) for row in doc.hints],
		)
		self.line(doc, FRENCH).override = 3000
		with self.assertRaisesRegex(frappe.ValidationError, "needs a Begründung"):
			doc.save()
		doc.reload()
		row = self.line(doc, FRENCH)
		row.override = 3000
		row.override_reason = "Die Nummer war am Leistungstag laut Bestätigung vom 2. Juni 2026 gültig."
		doc.save()
		doc.reload()
		self.assertEqual((doc.status, doc.ready), ("Bereit", 1))
		self.assertEqual(
			(self.line(doc, FRENCH).blocked, money(self.line(doc, FRENCH).reported)), (0, money(3000))
		)
		doc.calculate()
		doc.reload()
		self.assertEqual(
			(doc.status, self.line(doc, FRENCH).override_reason),
			("Bereit", "Die Nummer war am Leistungstag laut Bestätigung vom 2. Juni 2026 gültig."),
		)

	def test_a_line_of_its_own_with_a_reason_is_reported_and_kept(self):
		"""A Verbringen (§ 6a Absatz 2 UStG) is reported under the company's own USt-IdNr. in the other member
		state, with an override for a line without vouchers."""
		doc = self.statement(8)
		doc.append(
			"lines",
			{
				"vat_id": "ESX1234567X",
				"art": "L",
				"override": 5000,
				"override_reason": "Verbringen nach Madrid",
			},
		)
		doc.save()
		doc.calculate()
		doc.reload()
		spanish = self.line(doc, "ESX1234567X")
		self.assertEqual(
			(money(spanish.amount), money(spanish.reported), spanish.blocked, spanish.in_file),
			(money(0), money(5000), 0, 1),
		)
		self.assertEqual(money(doc.total_l), money(14800))

	def test_a_berichtigung_reports_what_changed_against_the_filing(self):
		doc = self.calculated(7)
		doc.remarks = "Die USt-IdNrn. sind am Liefertag bestätigt worden."
		doc.save()
		doc.mark_filed_outside(filed_via="mein_elster", transferticket=TICKET)
		doc.reload()
		self.assertEqual(
			(doc.docstatus, doc.status, doc.filed_via, doc.filed_on, doc.transferticket, doc.filed_by),
			(1, "Abgegeben", "mein_elster", getdate(today()), TICKET, "Administrator"),
		)
		with self.assertRaisesRegex(frappe.ValidationError, "is filed already as"):
			self.statement(7)
		a = self.account
		post_sales_invoice(
			COMPANY, "SINV-STZM-07-3", ALPEN, "2026-07-25", [(a["1400"], 500, 0), (a["8125"], 0, 500)]
		)
		correction = frappe.get_doc(DOCTYPE, doc.make_correction())
		self.assertEqual(
			(correction.meldeart, correction.corrects, correction.status, correction.period_label),
			("Berichtigung", doc.name, "Berechnet", "Juli 2026"),
		)
		self.assertEqual(
			[
				(row.vat_id, row.art, money(row.reported), money(row.filed_amount), row.in_file)
				for row in correction.lines
			],
			[(AUSTRIAN, "L", money(10300), money(9800), 1), (FRENCH, "S", money(3000), money(3000), 0)],
		)
		with self.assertRaisesRegex(frappe.ValidationError, "is a draft for Juli 2026 already"):
			doc.make_correction()
		correction.remarks = "Nachberechnung nach der Lieferung vom 25. Juli 2026."
		correction.save()
		url = correction.make_csv_file()
		self.assertEqual(
			frappe.db.get_value("File", {"file_url": url}, "file_name"), "ZM-2026-07-berichtigt.csv"
		)
		self.assertEqual(contents(url), HEADER + b"ATU12345678,10300,L")
		correction.mark_filed_outside(filed_via="mein_elster")
		doc.reload()
		correction.reload()
		self.assertEqual((doc.status, correction.status), ("Ersetzt", "Abgegeben"))
		with self.assertRaisesRegex(frappe.ValidationError, "latest filed Zusammenfassende Meldung"):
			doc.make_correction()

	def test_a_statement_is_filed_only_through_the_filing_marks(self):
		doc = self.statement(8)
		with self.assertRaisesRegex(frappe.ValidationError, "Calculate the statement before filing it"):
			doc.mark_filed_outside(filed_via="mein_elster")
		doc.reload()
		doc.calculate()
		doc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "not by Buchen alone"):
			doc.submit()
		doc.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "The statement is not ready"):
			doc.mark_filed_outside(filed_via="mein_elster")
		doc.reload()
		for arguments, message in (
			({"filed_via": "other_way"}, "Note how and when the statement was filed"),
			({"filed_via": "fax"}, "knows no way of filing"),
			({"filed_via": "mein_elster", "transferticket": "123"}, "is no Transferticket"),
			({"filed_via": "mein_elster", "filed_on": add_days(today(), 1)}, "cannot be filed in the future"),
		):
			with self.subTest(arguments=arguments), self.assertRaisesRegex(frappe.ValidationError, message):
				doc.mark_filed_outside(**arguments)
		doc.reload()
		doc.remarks = "Die Bestätigungen liegen der Steuerberatung vor."
		doc.save()
		note = "Am 20. September 2026 von der Steuerberatung im BZSt-Online-Portal abgegeben"
		doc.mark_filed_outside(remarks=note, filed_via="other_way")
		doc.reload()
		self.assertEqual(
			(doc.docstatus, doc.status, doc.filed_via, doc.filing_note), (1, "Abgegeben", "other_way", note)
		)
		with self.assertRaisesRegex(
			frappe.ValidationError, "Only a draft Zusammenfassende Meldung can be calculated"
		):
			doc.calculate()
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be cancelled"):
			doc.cancel()
		self.assertTrue(doc.make_csv_file())

	def test_a_quarterly_rhythm_above_the_threshold_holds_the_statement(self):
		doc = self.statement(1, company=QUARTERLY_COMPANY, kind="quarter")
		self.assertEqual(
			(doc.period_label, doc.quart, doc.deadline), ("I. Kalendervierteljahr 2026", 1, date(2026, 4, 27))
		)
		doc.calculate()
		doc.reload()
		(threshold,) = (row for row in doc.hints if row.code == "ZM-SCHWELLE")
		self.assertEqual(threshold.severity, "Fehler")
		self.assertIn("Ab Januar 2026 ist die ZM deshalb monatlich abzugeben", threshold.text)
		self.assertEqual(doc.status, "Berechnet")
		row = self.line(doc, AUSTRIAN)
		row.override = 60000
		row.override_reason = "Die Nummer ist bestätigt."
		doc.save()
		doc.reload()
		self.assertEqual((self.line(doc, AUSTRIAN).blocked, doc.status), (0, "Berechnet"))

	def test_the_period_comes_from_the_rhythm_of_the_settings(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "give no Zusammenfassende Meldung for Januar 2026"
		):
			self.statement(1, company=QUARTERLY_COMPANY)
		with self.assertRaisesRegex(frappe.ValidationError, "There is no Meldezeitraum 13"):
			self.statement(13)
		with self.assertRaisesRegex(frappe.ValidationError, "both the Anzeige and its Widerruf"):
			self.statement(3, anzeige=1, widerruf=1)
		with self.assertRaisesRegex(
			frappe.ValidationError, "comes only with a monthly Zusammenfassende Meldung"
		):
			self.statement(1, company=QUARTERLY_COMPANY, kind="quarter", anzeige=1)

	def test_a_company_needs_the_rhythm_of_the_zm_and_its_own_ust_idnr(self):
		company = make_company("Steuerbote Test ZM ohne Regeln GmbH", "STZO")
		make_settings(company, [(2026, "monthly", 1)])
		with self.assertRaisesRegex(frappe.ValidationError, "no rhythm of the Zusammenfassende Meldung yet"):
			self.statement(3, company=company)
		doc = self.calculated(3)
		frappe.db.set_value("VAT Return Settings", COMPANY, "ust_idnr", None)
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "Enter the USt-IdNr."),
		):
			doc.confirm_vat_ids()
		enqueue.assert_not_called()
		frappe.db.set_value("VAT Return Settings", COMPANY, "ust_idnr", OWN_VAT_ID)

	def test_a_running_confirmation_keeps_the_statement_as_it_is(self):
		doc = self.calculated(3)
		with patch("frappe.enqueue"):
			doc.confirm_vat_ids()
		doc.reload()
		doc.remarks = "Eine Änderung während der Prüfung"
		with self.assertRaisesRegex(frappe.ValidationError, "are being confirmed"):
			doc.save()
		with (
			patch.object(controller, "is_job_enqueued", return_value=True),
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "Wait for the result"),
		):
			doc.confirm_vat_ids()
		enqueue.assert_not_called()
		doc.reload()
		with patch.object(controller, "is_job_enqueued", return_value=False):
			doc.run_method("onload")
			self.assertTrue(doc.get_onload()["confirmation"]["stale"])
			doc.release_stale_confirmation()
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "confirmation_in_progress"), 0)
