"""USt-IdNrn. prüfen at the Umsatzsteuer-Voranmeldung and the hints of Berechnen on the confirmations of the
USt-IdNrn. behind Kz 41, 42 and 21, against invoices and payments written as ERPNext keeps them.

The confirmation runs through the real core of steuerbote.vatid; FakeBzst stands in for the transport and answers
as the eVatR API of the BZSt does, so no test reaches the network.
"""

from datetime import UTC, datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from steuerbote.steuerbote.doctype.vat_id_confirmation import confirming
from steuerbote.steuerbote.doctype.vat_id_confirmation.vat_id_confirmation import store
from steuerbote.steuerbote.doctype.vat_return import vat_return as controller
from steuerbote.steuerbote.doctype.vat_return.vat_return import run_confirmation
from steuerbote.tests.helpers import (
	make_account,
	make_company,
	make_customer,
	make_mapping,
	make_settings,
	post_payment_entry,
	post_sales_invoice,
)
from steuerbote.vatid.service import confirm
from steuerbote.vatid.tests.fakes import FakeBzst, FakeClock, FakeFetch, bzst

# The company, its accounts, customers and vouchers are made by the tests themselves.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Account", "Company", "DocType"]

DOCTYPE = "VAT Return"
SETTINGS = "VAT Return Settings"
CONFIRMATION = "VAT ID Confirmation"
# Files monthly from January 2026 and sells in October 2026 to customers in Austria, France and Italy and in
# Germany, in November 2026 in Germany alone.
COMPANY = "Steuerbote Test Voranmeldung USt-IdNr. GmbH"
# The example numbers of the OpenAPI document of the eVatR API and invented ones of France, Italy and Germany.
OWN_VAT_ID = "DE123456789"
AUSTRIAN = "ATU12345678"
FRENCH = "FR12345678901"
ITALIAN = "IT12345678901"
ALPEN = "Alpen Handel GmbH (UStVA)"
PARIS = "Paris Services SA (UStVA)"
ROMA = "Roma Commercio Srl (UStVA)"
MUENCHEN = "Münchner Einkauf GmbH (UStVA)"
CODES = ("USTIDNR-UNGEPRUEFT", "USTIDNR-VERALTET", "USTIDNR-UNGUELTIG")
QUALIFIED = {"ergFirmenname": "A", "ergStrasse": "A", "ergPlz": "A", "ergOrt": "A"}

# SKR03: intra-community deliveries and their Skonti (Kz 41), Dreiecksgeschäfte (Kz 42), EU services (Kz 21),
# sales at 19 % (Kz 81) with their tax, receivables and a bank.
ACCOUNTS = {
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"8743": ("Gewährte Skonti innergemeinschaftliche Lieferungen", "Income"),
	"8130": ("Lieferungen des ersten Abnehmers bei Dreiecksgeschäften", "Income"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
	"1400": ("Forderungen aus Lieferungen und Leistungen", "Asset"),
	"1200": ("Bank", "Asset"),
}


def vat_id_rows(doc) -> list:
	return [row for row in doc.hints if row.code in CODES]


def at(year: int, month: int, day: int):
	"""A clock that stands at noon of the day, so that the day is the same in the time zone of any site."""
	return lambda: datetime(year, month, day, 12, 0, tzinfo=UTC)


class TestVatIdConfirmationOfTheReturn(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STUC")
		a = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(
			COMPANY,
			[(2026, "monthly", 1)],
			ust_idnr=OWN_VAT_ID,
			zm_rules=[{"year": 2026, "valid_from_month": 1, "rhythm": "monthly"}],
		)
		make_mapping(COMPANY)
		alpen = make_customer(ALPEN, "Austria", AUSTRIAN, city="Wien")
		paris = make_customer(PARIS, "France", FRENCH, city="Paris")
		roma = make_customer(ROMA, "Italy", ITALIAN, city="Roma")
		make_customer(MUENCHEN, "Germany", "DE987654321", city="München")
		invoice = post_sales_invoice(
			COMPANY,
			"SINV-STUC-10-1",
			ALPEN,
			"2026-10-05",
			[(a["1400"], 10000, 0), (a["8125"], 0, 10000)],
			customer_address=alpen,
		)
		post_payment_entry(
			COMPANY,
			"PE-STUC-10-1",
			ALPEN,
			"2026-10-20",
			[invoice],
			[(a["1200"], 9800, 0), (a["8743"], 200, 0), (a["1400"], 0, 10000)],
		)
		post_sales_invoice(
			COMPANY,
			"SINV-STUC-10-2",
			PARIS,
			"2026-10-06",
			[(a["1400"], 3000, 0), (a["8336"], 0, 3000)],
			customer_address=paris,
		)
		post_sales_invoice(
			COMPANY,
			"SINV-STUC-10-3",
			ROMA,
			"2026-10-07",
			[(a["1400"], 5000, 0), (a["8130"], 0, 5000)],
			customer_address=roma,
		)
		for name, day in (("SINV-STUC-10-4", "2026-10-08"), ("SINV-STUC-11-1", "2026-11-05")):
			post_sales_invoice(
				COMPANY,
				name,
				MUENCHEN,
				day,
				[(a["1400"], 1190, 0), (a["8400"], 0, 1000), (a["1776"], 0, 190)],
			)

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("vat_id_confirmation_test")
		self.addCleanup(frappe.db.rollback, save_point="vat_id_confirmation_test")

	def vat_return(self, month: int):
		return frappe.get_doc(
			{"doctype": DOCTYPE, "company": COMPANY, "year": 2026, "rhythm": "monthly", "period_index": month}
		).insert()

	def calculated(self, month: int = 10):
		doc = self.vat_return(month)
		doc.calculate()
		doc.reload()
		return doc

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

	def stored(self, vat_id: str, clock, *answers) -> str:
		"""A confirmation of the company from elsewhere, such as a Zusammenfassende Meldung, asked at the clock and
		answered as given, by default as valid."""
		fetch = FakeFetch(*(answers or (bzst("evatr-0000"),)))
		return store(confirm(vat_id, OWN_VAT_ID, None, fetch, clock), COMPANY)

	def test_berechnen_names_each_unconfirmed_number_behind_kz_41_42_and_21_once(self):
		doc = self.calculated()
		self.assertEqual((doc.status, doc.ready), ("Bereit", 1))
		rows = vat_id_rows(doc)
		self.assertEqual(
			[
				(row.severity, row.code, row.party, row.voucher_type or None, row.voucher_no or None)
				for row in rows
			],
			[
				("Hinweis", "USTIDNR-UNGEPRUEFT", ALPEN, None, None),
				("Hinweis", "USTIDNR-UNGEPRUEFT", PARIS, None, None),
				("Hinweis", "USTIDNR-UNGEPRUEFT", ROMA, None, None),
			],
		)
		unconfirmed = "ist nicht bestätigt. „USt-IdNrn. prüfen“ lässt sie beim BZSt bestätigen."
		self.assertEqual(
			[row.text for row in rows],
			[
				f"Die USt-IdNr. {number} des Kunden {customer} (Kz {kennzahl}) {unconfirmed}"
				for number, customer, kennzahl in (
					(AUSTRIAN, ALPEN, 41),
					(FRENCH, PARIS, 21),
					(ITALIAN, ROMA, 42),
				)
			],
		)

	def test_ust_idnrn_pruefen_asks_the_bzst_about_each_number_and_gives_the_hints_anew(self):
		doc = self.calculated()
		others = [(row.code, row.text) for row in doc.hints if row.code not in CODES]
		service = FakeBzst(
			{
				AUSTRIAN: [bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED)],
				FRENCH: [bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED)],
				ITALIAN: [bzst("evatr-2001", 404)],
			}
		)
		numbers, call, commit, publish = self.confirm(doc, service)
		self.assertEqual(numbers, 3)
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
				(OWN_VAT_ID, ITALIAN, None, None),
			],
		)
		self.assertEqual(commit.call_count, 3)
		records = frappe.get_all(
			CONFIRMATION,
			filters={"vat_return": doc.name},
			fields=["requested", "qualified", "result", "company", "recapitulative_statement"],
			order_by="creation asc",
		)
		self.assertEqual(
			[(record.requested, record.qualified, record.result, record.company) for record in records],
			[
				(AUSTRIAN, 0, "valid", COMPANY),
				(AUSTRIAN, 1, "valid", COMPANY),
				(FRENCH, 0, "valid", COMPANY),
				(FRENCH, 1, "valid", COMPANY),
				(ITALIAN, 0, "invalid", COMPANY),
			],
		)
		self.assertEqual({record.recapitulative_statement for record in records}, {None})
		(event,) = (call for call in publish.call_args_list if call.args[0] == confirming.CONFIRMATION_EVENT)
		self.assertEqual(
			event.args[1],
			{"document_type": DOCTYPE, "document": doc.name, "confirmed": 3, "failed": [], "error": None},
		)
		self.assertEqual((doc.confirmation_in_progress, doc.status, doc.ready), (0, "Bereit", 1))
		self.assertEqual(
			[(row.severity, row.code, row.party) for row in vat_id_rows(doc)],
			[("Warnung", "USTIDNR-UNGUELTIG", ROMA)],
		)
		self.assertEqual(
			(doc.hints[0].code, doc.hints[0].text),
			(
				"USTIDNR-UNGUELTIG",
				f"Die USt-IdNr. {ITALIAN} des Kunden {ROMA} (Kz 42) ist laut Bestätigungsabfrage vom "
				"20. November 2026 ungültig.",
			),
		)
		self.assertEqual([(row.code, row.text) for row in doc.hints if row.code not in CODES], others)

	def test_a_confirmation_lies_at_most_the_days_of_the_settings_before_the_end_of_the_period(self):
		"""The latest confirmation of a number of the company counts, wherever it was asked; it holds for the
		moment of its query, so the hint says how long before the end of the period that was."""
		self.stored(AUSTRIAN, at(2026, 7, 1))
		self.stored(FRENCH, at(2026, 9, 15))
		self.stored(ITALIAN, at(2026, 11, 2))
		doc = self.calculated()
		stale = (
			f"Die USt-IdNr. {AUSTRIAN} des Kunden {ALPEN} (Kz 41) ist zuletzt am 1. Juli 2026 bestätigt worden, "
			"122 Tage vor dem Ende des Voranmeldungszeitraums Oktober 2026; die Einstellungen lassen höchstens 90 "
			"Tage zu. „USt-IdNrn. prüfen“ fragt erneut."
		)
		self.assertEqual(
			[(row.code, row.party, row.text) for row in vat_id_rows(doc)],
			[("USTIDNR-VERALTET", ALPEN, stale)],
		)
		self.assertEqual(frappe.db.get_value(SETTINGS, COMPANY, "max_confirmation_age"), 90)
		frappe.db.set_value(SETTINGS, COMPANY, "max_confirmation_age", 30)
		doc.calculate()
		doc.reload()
		self.assertEqual(
			[(row.code, row.party) for row in vat_id_rows(doc)],
			[("USTIDNR-VERALTET", ALPEN), ("USTIDNR-VERALTET", PARIS)],
		)
		self.stored(AUSTRIAN, at(2026, 11, 20), bzst("evatr-2001", 404))
		frappe.db.set_value(SETTINGS, COMPANY, "max_confirmation_age", 200)
		doc.calculate()
		doc.reload()
		self.assertEqual(
			[(row.severity, row.code, row.party) for row in vat_id_rows(doc)],
			[("Warnung", "USTIDNR-UNGUELTIG", ALPEN)],
		)

	def test_a_query_without_an_answer_leaves_the_number_unconfirmed(self):
		self.stored(AUSTRIAN, at(2026, 11, 20), OSError("timed out"), OSError("timed out"))
		doc = self.calculated()
		(row,) = (row for row in vat_id_rows(doc) if row.party == ALPEN)
		self.assertEqual(
			(row.code, row.text),
			(
				"USTIDNR-UNGEPRUEFT",
				f"Die USt-IdNr. {AUSTRIAN} des Kunden {ALPEN} (Kz 41) ist nicht bestätigt: Die Bestätigungsabfrage "
				"vom 20. November 2026 ergab kein Ergebnis. „USt-IdNrn. prüfen“ fragt erneut.",
			),
		)

	def test_only_a_calculated_draft_with_numbers_to_confirm_and_an_own_ust_idnr_asks(self):
		draft = self.vat_return(10)
		with patch("frappe.enqueue") as enqueue:
			with self.assertRaisesRegex(frappe.ValidationError, "Calculate the return before confirming"):
				draft.confirm_vat_ids()
			november = self.calculated(11)
			self.assertEqual(vat_id_rows(november), [])
			with self.assertRaisesRegex(frappe.ValidationError, "No customer behind Kz 41, 42 or 21"):
				november.confirm_vat_ids()
			doc = self.calculated()
			frappe.db.set_value(SETTINGS, COMPANY, "ust_idnr", None)
			with self.assertRaisesRegex(frappe.ValidationError, "Enter the USt-IdNr."):
				doc.confirm_vat_ids()
			frappe.db.set_value(SETTINGS, COMPANY, "ust_idnr", OWN_VAT_ID)
			doc.db_set("transmission_in_progress", 1)
			with self.assertRaisesRegex(frappe.ValidationError, "A transmission of .* is running"):
				doc.confirm_vat_ids()
			doc.db_set("transmission_in_progress", 0)
			doc.mark_filed_outside("In Mein ELSTER abgegeben")
			with self.assertRaisesRegex(frappe.ValidationError, "Only the USt-IdNrn. of a draft return"):
				doc.confirm_vat_ids()
		enqueue.assert_not_called()
		self.assertEqual(frappe.get_all(CONFIRMATION, filters={"vat_return": doc.name}), [])

	def test_a_running_confirmation_keeps_the_return_as_it_is(self):
		doc = self.calculated()
		with patch("frappe.enqueue"):
			doc.confirm_vat_ids()
		doc.reload()
		self.assertEqual(doc.confirmation_in_progress, 1)
		doc.remarks = "Eine Änderung während der Prüfung"
		with self.assertRaisesRegex(
			frappe.ValidationError, "are being confirmed. Wait for the result before"
		):
			doc.save()
		doc.reload()
		with self.assertRaisesRegex(
			frappe.ValidationError, "are being confirmed. Wait for the result before"
		):
			doc.calculate()
		doc.reload()
		with (
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "are being confirmed. Wait for the result"),
		):
			doc.transmit("validate")
		enqueue.assert_not_called()
		doc.reload()
		with (
			patch.object(confirming, "is_job_enqueued", return_value=True),
			patch("frappe.enqueue") as enqueue,
			self.assertRaisesRegex(frappe.ValidationError, "Wait for the result"),
		):
			doc.confirm_vat_ids()
		enqueue.assert_not_called()
		doc.reload()
		with patch.object(confirming, "is_job_enqueued", return_value=False):
			doc.run_method("onload")
			self.assertTrue(doc.get_onload()["confirmation"]["stale"])
			doc.release_stale_confirmation()
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "confirmation_in_progress"), 0)
