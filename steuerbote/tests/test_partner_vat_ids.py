"""The confirmations of the USt-IdNrn. of customers and suppliers on the site: the status on the partner, the triggers
of a change and of the button, the background job and the daily renewal against the fake transport, the check of a
Sales Invoice behind Kz 41, 42 or 21 on submit, the worklist, the connections of a partner and the steps of the setup.

The confirmations run through the real core of steuerbote.vatid; FakeBzst stands in for the transport and answers as
the eVatR API of the BZSt does, so no test reaches the network. The partners are written as ERPNext keeps them, so the
tests call the hooks themselves.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate

from steuerbote.setup.steps import Outcome
from steuerbote.steuerbote import partner_vat_ids as partner_module
from steuerbote.steuerbote import vat_id_setup
from steuerbote.steuerbote.doctype.vat_id_confirmation.vat_id_confirmation import store
from steuerbote.steuerbote.report.partner_ohne_aktuelle_ust_idnr_bestätigung import (
	partner_ohne_aktuelle_ust_idnr_bestätigung as worklist_report,
)
from steuerbote.tests.helpers import (
	insert_record,
	make_account,
	make_company,
	make_customer,
	make_mapping,
	make_settings,
	make_user,
)
from steuerbote.vatid.exemption import consequence
from steuerbote.vatid.service import confirm
from steuerbote.vatid.tests.fakes import FakeBzst, FakeFetch, bzst

SETTINGS = "VAT Return Settings"
CONFIRMATION = "VAT ID Confirmation"
COMPANY = "Steuerbote Test Partner USt-IdNr. GmbH"
OTHER = "Steuerbote Test Partner ohne USt-IdNr. GmbH"
# The example numbers of the OpenAPI document of the eVatR API and invented ones.
OWN_VAT_ID = "DE123456788"
AUSTRIAN = "ATU12345678"
FRENCH = "FR12345678901"
ITALIAN = "IT12345678901"
ALPEN = "Alpen Handel GmbH (Partner)"
PARIS = "Paris Services SA (Partner)"
MUENCHEN = "Münchner Einkauf GmbH (Partner)"
FORMFEHLER = "Formfehler Sp. z o.o. (Partner)"
ZUERICH = "Zürcher Werkstatt AG (Partner)"
NOWHERE = "Ohne Adresse SRL (Partner)"
ROMA = "Roma Fornitore Srl (Partner)"
QUALIFIED = {"ergFirmenname": "A", "ergStrasse": "A", "ergPlz": "A", "ergOrt": "A"}
ACCOUNTS = {
	"8125": ("Steuerfreie innergemeinschaftliche Lieferungen", "Income"),
	"8336": ("Erlöse sonstige Leistungen EU", "Income"),
	"8400": ("Erlöse 19 % USt", "Income"),
	"1776": ("Umsatzsteuer 19 %", "Liability"),
}


def noon(days: int = 0):
	"""A clock at noon of the day of the site, so that the day is the same in the time zone of any site and the
	services answer."""
	day = getdate(add_days(getdate(), days))
	return lambda: datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC)


def deals_with(party_type: str, party: str, company: str) -> None:
	insert_record(
		"Party Account",
		name=f"{party}-{company}",
		parent=party,
		parenttype=party_type,
		parentfield="accounts",
		idx=1,
		company=company,
	)


class TestPartnerVatIds(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_company(COMPANY, "STPU")
		make_company(OTHER, "STPO")
		cls.accounts = {
			number: make_account(COMPANY, number, name, root_type)
			for number, (name, root_type) in ACCOUNTS.items()
		}
		make_settings(
			COMPANY,
			[(2026, "monthly", 1)],
			ust_idnr=OWN_VAT_ID,
			vat_id_check_on_change=1,
			vat_id_renewal=1,
		)
		make_settings(OTHER, [(2026, "monthly", 1)])
		make_mapping(COMPANY)
		make_customer(ALPEN, "Austria", AUSTRIAN, city="Wien")
		make_customer(PARIS, "France", FRENCH, city="Paris")
		make_customer(MUENCHEN, "Germany", "DE987654321", city="München")
		make_customer(FORMFEHLER, "Poland", "PL-12", city="Warszawa")
		make_customer(ZUERICH, "Switzerland", "CHE-123.456.789 MWST", city="Zürich")
		insert_record("Customer", name=NOWHERE, customer_name=NOWHERE, tax_id="RO1234567890")
		insert_record("Supplier", name=ROMA, supplier_name=ROMA, tax_id=ITALIAN)
		for party_type, party in (
			("Customer", ALPEN),
			("Customer", PARIS),
			("Customer", MUENCHEN),
			("Customer", FORMFEHLER),
			("Customer", ZUERICH),
			("Customer", NOWHERE),
			("Supplier", ROMA),
		):
			deals_with(party_type, party, COMPANY)

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("partner_vat_id_test")
		self.addCleanup(frappe.db.rollback, save_point="partner_vat_id_test")

	def stored(self, vat_id: str, clock, *answers, details=None, party=None) -> str:
		"""A confirmation of the company asked at the clock and answered as given, by default as valid."""
		fetch = FakeFetch(*(answers or (bzst("evatr-0000"),)))
		return store(confirm(vat_id, OWN_VAT_ID, details, fetch, clock), COMPANY, party=party)

	def run_job(self, service, clock=None, **kwargs):
		with (
			patch.object(partner_module, "UrllibFetch", lambda: service),
			patch.object(partner_module, "_clock", clock or noon()),
			patch("frappe.db.commit") as commit,
			patch("frappe.publish_realtime") as publish,
		):
			partner_module.run_party_confirmation(**kwargs)
		return commit, publish

	def renew(self, service, clock=None):
		"""The daily renewal of the company of the tests alone, against the fake transport."""
		with (
			patch.object(
				partner_module,
				"policies",
				lambda: list(filter(None, [partner_module.company_policy(COMPANY)])),
			),
			patch.object(partner_module, "UrllibFetch", lambda: service),
			patch.object(partner_module, "_clock", clock or noon()),
			patch.object(partner_module.time, "sleep") as sleep,
			patch("frappe.db.commit"),
		):
			partner_module.renew_confirmations()
		return sleep

	def invoice(self, customer: str, account: str, **fields):
		return frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": COMPANY,
				"customer": customer,
				"customer_name": customer,
				"tax_id": frappe.db.get_value("Customer", customer, "tax_id"),
				"posting_date": getdate(),
				"items": [{"item_name": "Leistung", "qty": 1, "rate": 100, "income_account": account}],
				**fields,
			}
		)

	# The status and the triggers

	def test_the_status_of_a_partner_follows_its_number(self):
		statuses = {
			party: partner_module.refresh_status("Customer", party)["vat_id_status"]
			for party in (ALPEN, MUENCHEN, FORMFEHLER, ZUERICH)
		}
		self.assertEqual(
			statuses,
			{
				ALPEN: "Not Checked",
				MUENCHEN: "German VAT ID",
				FORMFEHLER: "Malformed",
				ZUERICH: "Not Confirmable",
			},
		)
		record = self.stored(AUSTRIAN, noon(), bzst("evatr-0000"))
		self.assertEqual(
			partner_module.refresh_status("Customer", ALPEN),
			{"vat_id_status": "Valid", "vat_id_checked_on": getdate(), "vat_id_confirmation": record},
		)
		self.assertEqual(frappe.db.get_value("Customer", ALPEN, "vat_id_status"), "Valid")

	def test_after_migrate_gives_each_partner_with_a_number_its_status_once(self):
		self.assertIn(
			"steuerbote.steuerbote.partner_vat_ids.fill_statuses",
			frappe.get_hooks("after_migrate", app_name="steuerbote"),
		)
		frappe.db.set_value("Customer", FORMFEHLER, "vat_id_status", None)
		frappe.db.set_value("Customer", MUENCHEN, "vat_id_status", "Valid")
		partner_module.fill_statuses()
		self.assertEqual(frappe.db.get_value("Customer", FORMFEHLER, "vat_id_status"), "Malformed")
		self.assertEqual(frappe.db.get_value("Customer", MUENCHEN, "vat_id_status"), "Valid")

	def test_nothing_is_sent_by_itself_until_the_automatic_check_is_switched_on(self):
		"""Both automatic triggers are off by default; the button works all the same."""
		fields = frappe.get_meta(SETTINGS)
		self.assertEqual(
			[fields.get_field(name).default for name in ("vat_id_check_on_change", "vat_id_renewal")],
			["0", "0"],
		)
		frappe.db.set_value(SETTINGS, COMPANY, {"vat_id_check_on_change": 0, "vat_id_renewal": 0})
		with patch("frappe.enqueue") as enqueue:
			partner_module.on_party_update(frappe.get_doc("Customer", ALPEN))
			enqueue.assert_not_called()
			self.assertTrue(partner_module.confirm_vat_id("Customer", ALPEN))
		service = FakeBzst({})
		self.renew(service)
		self.assertEqual(service.requests, [])
		self.assertEqual(frappe.db.get_value("Customer", ALPEN, "vat_id_status"), "Not Checked")
		state = partner_module.vat_id_state("Customer", ALPEN)
		self.assertEqual(
			[(row["company"], row["automatic"]) for row in state["companies"]], [(COMPANY, False)]
		)
		_columns, _rows, message = worklist_report.execute({"company": COMPANY})
		self.assertIn("automatic check is off", message)

	def test_a_new_partner_and_a_changed_number_name_or_address_queue_a_confirmation(self):
		doc = frappe.get_doc("Customer", ALPEN)
		with patch("frappe.enqueue") as enqueue:
			partner_module.on_party_update(doc)
		(call,) = enqueue.call_args_list
		self.assertEqual(call.args, (partner_module.PARTY_JOB,))
		self.assertEqual(
			{
				key: call.kwargs[key]
				for key in ("queue", "job_id", "enqueue_after_commit", "party", "trigger")
			},
			{
				"queue": "long",
				"job_id": f"steuerbote:ustid:Customer:{ALPEN}",
				"enqueue_after_commit": True,
				"party": ALPEN,
				"trigger": "Partner Changed",
			},
		)
		self.assertEqual(doc.vat_id_status, "Not Checked")
		doc._doc_before_save = frappe.get_doc("Customer", ALPEN)
		with patch("frappe.enqueue") as enqueue:
			partner_module.on_party_update(doc)
			enqueue.assert_not_called()
			doc.customer_name = "Alpen Handel GmbH & Co KG"
			partner_module.on_party_update(doc)
			self.assertEqual(enqueue.call_count, 1)
		address = frappe.get_doc("Address", f"{ALPEN}-Billing")
		with patch("frappe.enqueue") as enqueue:
			partner_module.on_address_update(address)
			self.assertEqual(enqueue.call_args.kwargs["party"], ALPEN)

	def test_no_number_the_bzst_cannot_confirm_is_queued(self):
		with patch("frappe.enqueue") as enqueue:
			for party in (MUENCHEN, FORMFEHLER, ZUERICH):
				partner_module.on_party_update(frappe.get_doc("Customer", party))
			enqueue.assert_not_called()
			with self.assertRaisesRegex(frappe.ValidationError, "has no USt-IdNr. of another member state"):
				partner_module.confirm_vat_id("Customer", MUENCHEN)
		self.assertEqual(frappe.db.get_value("Customer", FORMFEHLER, "vat_id_status"), "Malformed")

	def test_a_change_asks_only_where_the_settings_confirm_on_a_change_and_suppliers_where_they_confirm_them(
		self,
	):
		frappe.db.set_value(SETTINGS, COMPANY, {"vat_id_check_on_change": 0, "vat_id_check_suppliers": 0})
		with patch("frappe.enqueue") as enqueue:
			partner_module.on_party_update(frappe.get_doc("Customer", ALPEN))
			partner_module.on_party_update(frappe.get_doc("Supplier", ROMA))
			enqueue.assert_not_called()
			self.assertTrue(partner_module.confirm_vat_id("Supplier", ROMA))
			self.assertEqual(enqueue.call_args.kwargs["trigger"], "Manual")
		frappe.db.set_value(SETTINGS, COMPANY, "ust_idnr", None)
		with self.assertRaisesRegex(frappe.ValidationError, "No company confirms USt-IdNrn. yet"):
			partner_module.confirm_vat_id("Customer", ALPEN)

	def test_the_button_asks_whoever_may_change_the_partner(self):
		with (
			patch.object(partner_module.frappe, "has_permission", return_value=False) as allowed,
			patch("frappe.enqueue") as enqueue,
		):
			self.assertFalse(partner_module.request("Customer", ALPEN, "Partner Changed"))
			enqueue.assert_not_called()
		allowed.assert_called_with("Customer", "write", ALPEN, throw=False)
		with self.assertRaisesRegex(frappe.ValidationError, "customer or a supplier"):
			partner_module.confirm_vat_id("Company", COMPANY)

	def test_only_who_may_send_data_off_the_site_asks(self):
		"""An Accounts User may change a customer, but only who may submit a VAT Return sends data to the BZSt."""
		user = make_user("steuerbote-partner-buchhaltung@example.com", "Accounts User")
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user(user)
		self.assertFalse(partner_module.may_ask("Customer", ALPEN))
		with patch("frappe.enqueue") as enqueue:
			self.assertFalse(partner_module.request("Customer", ALPEN, "Partner Changed"))
			with self.assertRaisesRegex(frappe.PermissionError, "permission to submit a VAT Return"):
				partner_module.confirm_vat_id("Customer", ALPEN)
		enqueue.assert_not_called()
		frappe.set_user("Administrator")
		self.assertTrue(partner_module.may_ask("Customer", ALPEN))

	# The job

	def test_the_job_asks_qualified_with_the_address_and_keeps_the_partner_and_the_trigger(self):
		service = FakeBzst({AUSTRIAN: [bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED)]})
		_commit, publish = self.run_job(
			service, party_type="Customer", party=ALPEN, trigger="Manual", user="a@b.c"
		)
		self.assertEqual(
			[
				(query["angefragteUstid"], query.get("firmenname"), query.get("ort"))
				for query in service.requests
			],
			[(AUSTRIAN, None, None), (AUSTRIAN, ALPEN, "Wien")],
		)
		records = frappe.get_all(
			CONFIRMATION,
			filters={"party": ALPEN},
			fields=["company", "party_type", "started_by", "qualified", "result"],
			order_by="creation asc",
		)
		self.assertEqual(
			[(row.company, row.party_type, row.started_by, row.qualified, row.result) for row in records],
			[(COMPANY, "Customer", "Manual", 0, "valid"), (COMPANY, "Customer", "Manual", 1, "valid")],
		)
		self.assertEqual(frappe.db.get_value("Customer", ALPEN, "vat_id_status"), "Valid")
		(event,) = (call for call in publish.call_args_list if call.args[0] == partner_module.PARTY_EVENT)
		self.assertEqual(
			(event.args[1], event.kwargs["user"]),
			(
				{"party_type": "Customer", "party": ALPEN, "status": "Valid", "asked": 1, "failed": []},
				"a@b.c",
			),
		)

	def test_a_question_answered_today_is_not_asked_again(self):
		self.stored(
			AUSTRIAN, noon(), bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED), details=self.details()
		)
		service = FakeBzst({})
		self.run_job(service, party_type="Customer", party=ALPEN, trigger="Manual")
		self.assertEqual(service.requests, [])
		self.assertEqual(frappe.db.count(CONFIRMATION, {"requested": AUSTRIAN, "company": COMPANY}), 2)

	def test_an_answer_of_another_day_or_without_the_address_is_asked_again(self):
		self.stored(
			AUSTRIAN, noon(-1), bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED), details=self.details()
		)
		self.stored(AUSTRIAN, noon(), bzst("evatr-0000"))
		service = FakeBzst({AUSTRIAN: [bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED)]})
		self.run_job(service, party_type="Customer", party=ALPEN, trigger="Manual")
		self.assertEqual(len(service.requests), 2)

	def details(self):
		return partner_module.party_details("Customer", ALPEN)

	def test_a_partner_without_an_address_is_asked_simply(self):
		self.assertIsNone(partner_module.party_details("Customer", NOWHERE))
		service = FakeBzst({"RO1234567890": [bzst("evatr-0000")]})
		self.run_job(service, party_type="Customer", party=NOWHERE, trigger="Manual")
		self.assertEqual([query.get("firmenname") for query in service.requests], [None])

	def test_a_failed_query_is_logged_and_the_job_goes_on(self):
		service = FakeBzst({})
		_commit, publish = self.run_job(service, party_type="Customer", party=ALPEN, trigger="Manual")
		(event,) = (call for call in publish.call_args_list if call.args[0] == partner_module.PARTY_EVENT)
		self.assertEqual((event.args[1]["failed"], event.args[1]["asked"]), ([COMPANY], 0))
		self.assertEqual(frappe.db.count(CONFIRMATION, {"party": ALPEN}), 0)

	# The renewal

	def test_the_renewal_asks_about_the_partners_due_one_after_the_other(self):
		self.stored(
			FRENCH, noon(-10), bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED), details=self.paris()
		)
		service = FakeBzst(
			{
				AUSTRIAN: [bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED)],
				"RO1234567890": [bzst("evatr-0000")],
				ITALIAN: [bzst("evatr-2001", 404)],
			}
		)
		sleep = self.renew(service)
		self.assertEqual(
			[query["angefragteUstid"] for query in service.requests],
			[AUSTRIAN, AUSTRIAN, ITALIAN, "RO1234567890"],
		)
		self.assertEqual(sleep.call_count, 2)
		self.assertEqual(
			set(frappe.get_all(CONFIRMATION, filters={"started_by": "Renewal"}, pluck="party")),
			{ALPEN, ROMA, NOWHERE},
		)
		self.assertEqual(frappe.db.get_value("Supplier", ROMA, "vat_id_status"), "Invalid")
		self.assertEqual(frappe.db.get_value("Customer", FORMFEHLER, "vat_id_status"), "Malformed")
		service = FakeBzst({})
		self.renew(service)
		self.assertEqual(service.requests, [], "no number twice a day")

	def test_the_renewal_stops_at_the_first_service_that_cannot_answer(self):
		"""The BZSt cannot answer the first number, VIES gets no connection; nothing else is asked that day."""
		service = FakeFetch(bzst("evatr-0011", 503), OSError("no connection"))
		self.renew(service)
		self.assertEqual(len(service.requests), 2)
		self.assertEqual(
			frappe.get_all(CONFIRMATION, filters={"started_by": "Renewal"}, pluck="requested"), [AUSTRIAN] * 2
		)

	def test_the_renewal_waits_for_the_hours_of_the_services_and_for_the_own_vat_id(self):
		service = FakeBzst({})
		self.renew(service, lambda: datetime(2026, 11, 25, 23, 30, tzinfo=UTC))
		frappe.db.set_value(SETTINGS, COMPANY, "vat_id_renewal", 0)
		self.renew(service)
		frappe.db.set_value(SETTINGS, COMPANY, {"vat_id_renewal": 1, "ust_idnr": None})
		self.renew(service)
		self.assertEqual(service.requests, [])
		self.assertIn(
			"steuerbote.steuerbote.partner_vat_ids.renew_confirmations",
			frappe.get_hooks("scheduler_events", app_name="steuerbote")["cron"]["30 6 * * *"],
		)

	def paris(self):
		return partner_module.party_details("Customer", PARIS)

	# The Sales Invoice

	def test_an_invoice_for_goods_needs_a_confirmation_of_its_day(self):
		doc = self.invoice(ALPEN, self.accounts["8125"])
		with self.assertRaisesRegex(
			frappe.ValidationError, f"The USt-IdNr. {AUSTRIAN} .* has no confirmation"
		):
			partner_module.check_invoice(doc)
		self.stored(AUSTRIAN, noon(-1))
		with self.assertRaisesRegex(frappe.ValidationError, "was last confirmed on .*, 1 days before"):
			partner_module.check_invoice(doc)
		record = self.stored(AUSTRIAN, noon())
		partner_module.check_invoice(doc)
		self.assertEqual(doc.vat_id_confirmation, record)

	def test_a_draft_invoice_confirms_its_customer_for_its_company_and_the_confirmation_names_it(self):
		frappe.db.delete("Party Account", {"parent": PARIS})
		invoice = insert_record(
			"Sales Invoice", name="SINV-STPU-ENTWURF", company=COMPANY, customer=PARIS, docstatus=0
		)
		frappe.db.set_single_value("Global Defaults", "default_company", OTHER)
		with patch("frappe.enqueue") as enqueue:
			self.assertTrue(partner_module.confirm_invoice_customer(invoice))
		self.assertEqual(
			{
				key: enqueue.call_args.kwargs[key]
				for key in ("party", "trigger", "source_doctype", "source_name")
			},
			{"party": PARIS, "trigger": "Invoice", "source_doctype": "Sales Invoice", "source_name": invoice},
		)
		service = FakeBzst({FRENCH: [bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED)]})
		job = ("party_type", "party", "trigger", "source_doctype", "source_name")
		self.run_job(service, **{key: enqueue.call_args.kwargs[key] for key in job})
		self.assertEqual(
			set(
				frappe.get_all(
					CONFIRMATION, filters={"party": PARIS}, fields=["company", "sales_invoice"], as_list=True
				)
			),
			{(COMPANY, invoice)},
		)
		frappe.db.set_value("Sales Invoice", invoice, "docstatus", 1)
		with self.assertRaisesRegex(frappe.ValidationError, "saved draft invoice"):
			partner_module.confirm_invoice_customer(invoice)

	def test_a_confirmation_of_the_same_day_after_a_refused_submit_lets_the_invoice_through(self):
		doc = self.invoice(ALPEN, self.accounts["8125"])
		with self.assertRaisesRegex(frappe.ValidationError, "Confirm VAT ID of the Customer") as refused:
			partner_module.check_invoice(doc)
		for step in ("Confirm VAT ID", "Reason for Releasing the VAT ID"):
			self.assertIn(step, str(refused.exception))
		service = FakeBzst({AUSTRIAN: [bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED)]})
		self.run_job(service, party_type="Customer", party=ALPEN, trigger="Invoice")
		partner_module.check_invoice(doc)
		self.assertEqual(frappe.db.get_value(CONFIRMATION, doc.vat_id_confirmation, "requested"), AUSTRIAN)

	def test_a_reason_submits_a_blocked_invoice_and_stays_on_it(self):
		doc = self.invoice(
			ALPEN, self.accounts["8125"], vat_id_release_reason="Bestätigung vom Liefertag in der Akte"
		)
		with patch("frappe.msgprint") as message:
			partner_module.check_invoice(doc)
		self.assertIn("released for this invoice", message.call_args.args[0])
		self.assertEqual(doc.vat_id_release_reason, "Bestätigung vom Liefertag in der Akte")

	def test_no_reason_releases_a_missing_or_wrong_number_and_the_refusal_says_what_it_costs(self):
		doc = self.invoice(
			MUENCHEN, self.accounts["8125"], vat_id_release_reason="Kunde sagt, er sei Unternehmer"
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Correct the USt-IdNr.") as refused:
			partner_module.check_invoice(doc)
		self.assertIn(consequence("41"), str(refused.exception))
		self.assertNotIn("Reason for Releasing the VAT ID", str(refused.exception))

	def test_an_invoice_for_services_warns_without_a_qualified_confirmation(self):
		doc = self.invoice(PARIS, self.accounts["8336"])
		self.stored(FRENCH, noon(-5))
		with patch("frappe.msgprint") as message:
			partner_module.check_invoice(doc)
		self.assertIn("without name and address", message.call_args.args[0])
		self.assertEqual(message.call_args.kwargs["indicator"], "orange")
		frappe.db.set_value(SETTINGS, COMPANY, "vat_id_invoice_services", "Block")
		with self.assertRaisesRegex(frappe.ValidationError, "without name and address"):
			partner_module.check_invoice(doc)

	def test_an_invoice_the_mapping_puts_elsewhere_or_a_credit_note_needs_nothing(self):
		with patch("frappe.msgprint") as message:
			partner_module.check_invoice(self.invoice(MUENCHEN, self.accounts["8400"]))
			partner_module.check_invoice(self.invoice(ALPEN, self.accounts["8125"], is_return=1))
			frappe.db.set_value(SETTINGS, COMPANY, "vat_id_invoice_goods", "Off")
			partner_module.check_invoice(self.invoice(ALPEN, self.accounts["8125"]))
			message.assert_not_called()
		self.assertIn(
			"steuerbote.steuerbote.partner_vat_ids.check_invoice",
			frappe.get_hooks("doc_events", app_name="steuerbote")["Sales Invoice"]["before_submit"],
		)

	def test_an_invoice_for_goods_to_a_customer_without_a_number_is_blocked(self):
		customer = insert_record(
			"Customer", name="Ohne Nummer GmbH (Partner)", customer_name="Ohne Nummer GmbH"
		)
		doc = self.invoice(customer, self.accounts["8125"])
		with self.assertRaisesRegex(
			frappe.ValidationError, "goes to Kz 41, but the customer .* has no USt-IdNr."
		):
			partner_module.check_invoice(doc)
		self.assertIsNone(doc.vat_id_confirmation)

	def test_a_german_number_on_an_invoice_for_goods_is_blocked(self):
		doc = self.invoice(MUENCHEN, self.accounts["8125"])
		with self.assertRaisesRegex(frappe.ValidationError, "is German; Kz 41 needs one"):
			partner_module.check_invoice(doc)

	# The worklist, the form and the setup

	def test_the_worklist_names_every_partner_without_a_current_confirmation(self):
		self.stored(FRENCH, noon(), bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED), details=self.paris())
		self.stored(AUSTRIAN, noon(-200))
		columns, rows, message = worklist_report.execute({"company": COMPANY})
		self.assertIsNone(message)
		self.assertEqual(
			sorted((row["party"], row["standing"]) for row in rows),
			sorted(
				[
					(ALPEN, "Expired"),
					(FORMFEHLER, "Malformed"),
					(NOWHERE, "Missing"),
					(ZUERICH, "Not Confirmable"),
					(ROMA, "Missing"),
				]
			),
		)
		self.assertEqual(
			[column["fieldname"] for column in columns][:4], ["party_type", "party", "tax_id", "standing"]
		)
		_columns, rows, _message = worklist_report.execute({"company": COMPANY, "party_type": "Supplier"})
		self.assertEqual([row["party"] for row in rows], [ROMA])
		_columns, rows, message = worklist_report.execute({"company": OTHER})
		self.assertEqual(rows, [])
		self.assertIn("has no own USt-IdNr.", message)

	def test_the_form_shows_where_the_confirmation_stands_and_the_connections_list_it(self):
		self.stored(AUSTRIAN, noon(), party=("Customer", ALPEN))
		state = partner_module.vat_id_state("Customer", ALPEN)
		self.assertEqual(
			(state["sent"], [(row["company"], row["standing"]) for row in state["companies"]]),
			(True, [(COMPANY, "Not Qualified")]),
		)
		self.assertEqual(partner_module.vat_id_state("Customer", ZUERICH)["companies"], [])
		for doctype in ("Customer", "Supplier"):
			with self.subTest(doctype=doctype):
				data = frappe.get_meta(doctype).get_dashboard_data()
				self.assertEqual(data.non_standard_fieldnames[CONFIRMATION], "party")
				self.assertEqual(data.dynamic_links["party"], [doctype, "party_type"])
				self.assertIn(CONFIRMATION, [item for group in data.transactions for item in group["items"]])

	def test_the_setup_offers_to_relabel_the_tax_id_and_leaves_a_label_of_its_own(self):
		context = SimpleNamespace(company=COMPANY)
		for doctype in vat_id_setup.LABELLED_DOCTYPES:
			frappe.db.delete(
				"Property Setter", {"doc_type": doctype, "field_name": "tax_id", "property": "label"}
			)
		self.addCleanup(self.forget_labels)
		result = vat_id_setup.check_tax_id_label(context)
		self.assertEqual(
			(result.outcome, result.action.method),
			(Outcome.UNDECIDED, f"{vat_id_setup.__name__}.relabel_tax_id"),
		)
		vat_id_setup.relabel_tax_id()
		self.assertEqual(frappe.get_meta("Customer").get_label("tax_id"), "VAT ID")
		self.assertEqual(vat_id_setup.check_tax_id_label(context).outcome, Outcome.SKIPPED)

	def forget_labels(self):
		"""Undo the Property Setters before the cache of the DocTypes is cleared, so that it does not keep them."""
		frappe.db.rollback(save_point="partner_vat_id_test")
		for doctype in vat_id_setup.LABELLED_DOCTYPES:
			frappe.clear_cache(doctype=doctype)

	def test_the_setup_offers_to_switch_on_the_automatic_check_of_the_company(self):
		context = SimpleNamespace(company=COMPANY)
		frappe.db.set_value(SETTINGS, COMPANY, {"vat_id_check_on_change": 0, "vat_id_renewal": 0})
		result = vat_id_setup.check_automatic_check(context)
		self.assertEqual(
			(result.outcome, result.action.method),
			(Outcome.UNDECIDED, f"{vat_id_setup.__name__}.enable_automatic_check"),
		)
		vat_id_setup.enable_automatic_check(COMPANY)
		self.assertEqual(
			frappe.db.get_value(SETTINGS, COMPANY, ["vat_id_check_on_change", "vat_id_renewal"]), (1, 1)
		)
		self.assertEqual(vat_id_setup.check_automatic_check(context).outcome, Outcome.SKIPPED)
		self.assertEqual(
			vat_id_setup.check_automatic_check(SimpleNamespace(company=OTHER)).outcome, Outcome.UNDECIDED
		)
		self.assertIsNone(vat_id_setup.check_automatic_check(SimpleNamespace(company=OTHER)).action)

	def test_the_setup_offers_to_stop_the_vat_id_job_of_erpnext_germany_where_it_runs(self):
		context = SimpleNamespace(company=COMPANY)
		with patch.object(vat_id_setup.frappe, "get_installed_apps", return_value=["frappe", "erpnext"]):
			self.assertEqual(vat_id_setup.check_erpnext_germany(context).outcome, Outcome.SKIPPED)
		job = insert_record(
			"Scheduled Job Type",
			name="steuerbote-test-germany",
			method=vat_id_setup.GERMANY_JOB,
			frequency="All",
		)
		apps = ["frappe", "erpnext", "erpnext_germany", "steuerbote"]
		with patch.object(vat_id_setup.frappe, "get_installed_apps", return_value=apps):
			result = vat_id_setup.check_erpnext_germany(context)
			self.assertEqual(
				(result.outcome, result.document), (Outcome.UNDECIDED, ("Scheduled Job Type", job))
			)
			vat_id_setup.stop_erpnext_germany_check()
			self.assertEqual(frappe.db.get_value("Scheduled Job Type", job, "stopped"), 1)
			self.assertEqual(vat_id_setup.check_erpnext_germany(context).outcome, Outcome.SKIPPED)
		self.assertEqual(
			[step["key"] for step in frappe.get_hooks("steuerbote_setup_steps", app_name="steuerbote")][-3:],
			["vat_id_label", "erpnext_germany_vat_id_check", "vat_id_automatic_check"],
		)
