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
	NUMBERED_CUSTOMER,
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
from steuerbote.vatid.tests.fakes import FakeBzst, FakeFetch, bzst, vies
from steuerbote.vatid.vies import URL as VIES_URL

SETTINGS = "VAT Return Settings"
CONFIRMATION = "VAT ID Confirmation"
COMPANY = "Steuerbote Test Partner USt-IdNr. GmbH"
OTHER = "Steuerbote Test Partner ohne USt-IdNr. GmbH"
# A second company of the group that asks under the same own USt-IdNr., as a copy of a company does.
TWIN = "Steuerbote Test Partner Zwilling GmbH"
# The example numbers of the OpenAPI document of the eVatR API and invented ones.
OWN_VAT_ID = "DE123456788"
AUSTRIAN = "ATU12345678"
FRENCH = "FR12345678901"
ITALIAN = "IT12345678901"
ALPEN = "Alpen Handel GmbH (Partner)"
PARIS = "Paris Services SA (Partner)"
MUENCHEN = "Münchner Einkauf GmbH (Partner)"
PRUEFZIFFER = "Falsche Prüfziffer GmbH (Partner)"
# Invented German numbers: the first with the right check digit, the second with a wrong one.
GERMAN = "DE987654328"
GERMAN_WRONG = "DE987654321"
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
			vat_id_check_german=0,
		)
		make_settings(OTHER, [(2026, "monthly", 1)])
		make_company(TWIN, "STPZ")
		make_settings(TWIN, [(2026, "monthly", 1)], ust_idnr=OWN_VAT_ID, vat_id_check_german=0)
		make_mapping(COMPANY)
		make_customer(ALPEN, "Austria", AUSTRIAN, city="Wien")
		make_customer(PARIS, "France", FRENCH, city="Paris")
		make_customer(MUENCHEN, "Germany", GERMAN, city="München")
		make_customer(PRUEFZIFFER, "Germany", GERMAN_WRONG, city="Köln")
		make_customer(FORMFEHLER, "Poland", "PL-12", city="Warszawa")
		make_customer(ZUERICH, "Switzerland", "CHE-123.456.789 MWST", city="Zürich")
		insert_record("Customer", name=NOWHERE, customer_name=NOWHERE, tax_id="RO1234567890")
		insert_record("Supplier", name=ROMA, supplier_name=ROMA, tax_id=ITALIAN)
		for party_type, party in (
			("Customer", ALPEN),
			("Customer", PARIS),
			("Customer", MUENCHEN),
			("Customer", PRUEFZIFFER),
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

	# The companies of a partner

	def new_customer(self, name: str = "Neuer Kunde AT GmbH (Partner)") -> str:
		"""A customer with a valid Austrian number that deals with no company yet."""
		make_customer(name, "Austria", "ATU99999999", city="Graz")
		return name

	def test_a_partner_without_dealings_is_asked_about_by_no_company_by_itself(self):
		"""Decision of the owner: the automatic check asks only the companies a partner deals with, on every site; the
		default company takes no partner. The button asks for the company of the user."""
		customer = self.new_customer()
		frappe.db.set_single_value("Global Defaults", "default_company", COMPANY)
		self.assertEqual(partner_module.companies_for("Customer", customer, partner_module.CHANGED), [])
		with patch("frappe.enqueue") as enqueue:
			self.assertFalse(partner_module.request("Customer", customer, partner_module.CHANGED))
		enqueue.assert_not_called()
		self.assertNotIn(
			customer,
			[
				party
				for _type, party, _id in partner_module.partners_of(partner_module.company_policy(COMPANY))
			],
		)
		with patch("frappe.defaults.get_user_default", return_value=COMPANY):
			manual = partner_module.companies_for("Customer", customer, partner_module.MANUAL)
		self.assertEqual([policy.company for policy in manual], [COMPANY])

	def test_a_submitted_quotation_or_order_makes_a_partner_deal_with_its_company(self):
		customer = self.new_customer()
		supplier = insert_record(
			"Supplier",
			name="Neuer Lieferant IT (Partner)",
			supplier_name="Neuer Lieferant IT",
			tax_id=ITALIAN,
		)
		self.assertEqual(partner_module.dealings("Customer", [customer]), {})
		insert_record(
			"Quotation",
			name="QTN-STPU-NEU",
			company=COMPANY,
			quotation_to="Customer",
			party_name=customer,
			docstatus=1,
		)
		insert_record("Purchase Order", name="PUR-STPU-NEU", company=COMPANY, supplier=supplier, docstatus=1)
		self.assertEqual(partner_module.dealings("Customer", [customer]), {customer: {COMPANY}})
		self.assertEqual(partner_module.dealings("Supplier", [supplier]), {supplier: {COMPANY}})
		draft = self.new_customer("Entwurf Kunde AT GmbH (Partner)")
		insert_record("Sales Order", name="SO-STPU-ENTWURF", company=COMPANY, customer=draft, docstatus=0)
		self.assertEqual(partner_module.dealings("Customer", [draft]), {})
		insert_record("Sales Order", name="SO-STPU-NEU", company=COMPANY, customer=draft, docstatus=1)
		self.assertEqual(partner_module.dealings("Customer", [draft]), {draft: {COMPANY}})

	def test_the_form_and_the_worklist_show_a_partner_that_deals_with_no_company(self):
		customer = self.new_customer()
		with patch("frappe.defaults.get_user_default", return_value=COMPANY):
			state = partner_module.vat_id_state("Customer", customer)
		self.assertFalse(state["assigned"])
		self.assertEqual([row["company"] for row in state["companies"]], [COMPANY])
		(row,) = [row for row in partner_module.worklist(COMPANY) if row["party"] == customer]
		self.assertEqual(row["standing"].value, "Not Assigned")
		self.assertTrue(partner_module.vat_id_state("Customer", ALPEN)["assigned"])

	# The status and the triggers

	def test_the_status_of_a_partner_follows_its_number(self):
		statuses = {
			party: partner_module.refresh_status("Customer", party)["vat_id_status"]
			for party in (ALPEN, MUENCHEN, PRUEFZIFFER, FORMFEHLER, ZUERICH)
		}
		self.assertEqual(
			statuses,
			{
				ALPEN: "Not Checked",
				MUENCHEN: "German VAT ID, Not Checked",
				PRUEFZIFFER: "Malformed",
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
		frappe.db.set_value("Customer", PRUEFZIFFER, "vat_id_status", "German VAT ID")
		frappe.db.set_value("Customer", ZUERICH, "vat_id_status", "Not Checked")
		partner_module.fill_statuses()
		self.assertEqual(frappe.db.get_value("Customer", PRUEFZIFFER, "vat_id_status"), "Malformed")
		self.assertEqual(frappe.db.get_value("Customer", ZUERICH, "vat_id_status"), "Not Confirmable")
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
		self.assertEqual(
			[row["standing_label"] for row in state["companies"]],
			["Not Checked"],
			"the form says what the field Stand der USt-IdNr. says",
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
			with self.assertRaisesRegex(frappe.ValidationError, "has no USt-IdNr. that a service checks"):
				partner_module.confirm_vat_id("Customer", PRUEFZIFFER)
			with self.assertRaisesRegex(frappe.ValidationError, "checks no German USt-IdNrn."):
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

	def test_companies_with_the_same_own_vat_id_ask_once_and_share_the_answer(self):
		"""VIES and the BZSt count the same question asked again on one day as misuse: the companies of a group that ask
		under the same own USt-IdNr. send it once, and each keeps the answer as its proof."""
		deals_with("Customer", ALPEN, TWIN)
		service = FakeBzst({AUSTRIAN: [bzst("evatr-0000"), bzst("evatr-0000", **QUALIFIED)]})
		self.run_job(service, party_type="Customer", party=ALPEN, trigger="Manual")
		self.assertEqual(
			[
				(query["anfragendeUstid"], query["angefragteUstid"], query.get("firmenname"))
				for query in service.requests
			],
			[(OWN_VAT_ID, AUSTRIAN, None), (OWN_VAT_ID, AUSTRIAN, ALPEN)],
		)
		records = frappe.get_all(
			CONFIRMATION,
			filters={"requested": AUSTRIAN},
			fields=["company", "qualified", "result", "requester", "consultation_id"],
			order_by="company asc, creation asc",
		)
		self.assertEqual(
			[(row.company, row.qualified, row.result, row.requester) for row in records],
			[
				(COMPANY, 0, "valid", OWN_VAT_ID),
				(COMPANY, 1, "valid", OWN_VAT_ID),
				(TWIN, 0, "valid", OWN_VAT_ID),
				(TWIN, 1, "valid", OWN_VAT_ID),
			],
		)
		self.assertEqual(records[0].consultation_id, records[2].consultation_id, "the same query")
		later = FakeBzst({})
		self.run_job(later, party_type="Customer", party=ALPEN, trigger="Manual")
		self.assertEqual(later.requests, [], "not again on the same day")

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

	def test_the_warning_of_an_invoice_for_services_names_the_next_step(self):
		"""A warning lets the invoice through, but says what proves the customer a Unternehmer: the qualified
		confirmation of its USt-IdNr. (UStAE 3a.2 Abs. 9), which the button on the customer asks for."""
		doc = self.invoice(PARIS, self.accounts["8336"])
		with patch("frappe.msgprint") as message:
			partner_module.check_invoice(doc)
		text = message.call_args.args[0]
		self.assertIn(f"The USt-IdNr. {FRENCH} of the customer", text)
		self.assertIn("has no confirmation", text)
		self.assertIn("„Confirm VAT ID“ on the customer", text)
		self.assertIn("UStAE 3a.2 Abs. 9", text)

	def test_a_german_number_with_a_wrong_check_digit_is_refused_for_its_check_digit(self):
		"""The invoice names what is wrong with the number as the form of the customer does, not the rule that the
		BZSt confirms no German number."""
		doc = self.invoice(PRUEFZIFFER, self.accounts["8125"])
		with self.assertRaisesRegex(
			frappe.ValidationError, "Die Prüfziffer von DE987654321 stimmt nicht"
		) as refused:
			partner_module.check_invoice(doc)
		self.assertNotIn("§ 18e Nr. 1 UStG", str(refused.exception))

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

	def test_the_refusal_of_an_invoice_is_a_message_without_a_traceback(self):
		"""The gate refuses as intended; the browser gets its message, not the traceback a System Manager sees for
		an error of the code (is_traceback_allowed of Frappe)."""
		self.addCleanup(frappe.local.flags.pop, "disable_traceback", None)
		customer = insert_record("Customer", name="Ohne Nummer AG (Partner)", customer_name="Ohne Nummer AG")
		with self.assertRaises(frappe.ValidationError):
			partner_module.check_invoice(self.invoice(customer, self.accounts["8125"]))
		self.assertTrue(frappe.local.flags.disable_traceback)

	def test_a_german_number_on_an_invoice_for_goods_is_blocked(self):
		doc = self.invoice(MUENCHEN, self.accounts["8125"])
		with self.assertRaisesRegex(frappe.ValidationError, "is German; Kz 41 needs one"):
			partner_module.check_invoice(doc)

	# The worklist, the form and the setup

	# German numbers

	def test_saving_a_partner_with_a_wrong_number_says_what_is_wrong(self):
		doc = frappe.get_doc("Customer", PRUEFZIFFER)
		with patch("frappe.msgprint") as message, patch("frappe.enqueue") as enqueue:
			partner_module.on_party_update(doc)
		enqueue.assert_not_called()
		self.assertIn("Die Prüfziffer von DE987654321 stimmt nicht", message.call_args.args[0])
		self.assertEqual(doc.vat_id_status, "Malformed")

	def test_a_german_number_is_checked_simply_at_vies_where_the_company_checks_german_numbers(self):
		self.assertEqual(frappe.get_meta(SETTINGS).get_field("vat_id_check_german").default, "1")
		frappe.db.set_value(SETTINGS, COMPANY, "vat_id_check_german", 1)
		with patch("frappe.enqueue") as enqueue:
			self.assertTrue(partner_module.confirm_vat_id("Customer", MUENCHEN))
		self.assertEqual(enqueue.call_args.kwargs["party"], MUENCHEN)
		service = FakeFetch(vies(True, countryCode="DE", vatNumber=GERMAN[2:]))
		self.run_job(service, party_type="Customer", party=MUENCHEN, trigger="Manual")
		self.assertEqual(service.urls(), [VIES_URL])
		self.assertNotIn("traderName", service.requests[0].body.decode())
		(record,) = frappe.get_all(
			CONFIRMATION,
			filters={"party": MUENCHEN},
			fields=["service", "qualified", "result", "requested", "started_by"],
		)
		self.assertEqual(
			(record.service, record.qualified, record.result, record.requested, record.started_by),
			("vies", 0, "valid", GERMAN, "Manual"),
		)
		self.assertEqual(frappe.db.get_value("Customer", MUENCHEN, "vat_id_status"), "Valid (Simple)")
		state = partner_module.vat_id_state("Customer", MUENCHEN)
		self.assertEqual(
			(state["kind"], [(row["company"], row["standing"]) for row in state["companies"]]),
			("german", [(COMPANY, "Current")]),
		)

	def test_the_renewal_checks_german_numbers_where_the_company_checks_them(self):
		frappe.db.set_value(SETTINGS, COMPANY, "vat_id_check_german", 1)
		for party in (ALPEN, NOWHERE, PARIS):
			self.stored(
				frappe.db.get_value("Customer", party, "tax_id"),
				noon(),
				bzst("evatr-0000"),
				party=("Customer", party),
			)
		self.stored(ITALIAN, noon(), bzst("evatr-0000"))
		service = FakeFetch(vies(False, countryCode="DE", vatNumber=GERMAN[2:]))
		self.renew(service)
		self.assertEqual(service.urls(), [VIES_URL])
		self.assertEqual(frappe.db.get_value("Customer", MUENCHEN, "vat_id_status"), "Invalid")

	def numbered_customer(self) -> str:
		"""The customer 10042 „Muster GmbH“ in Austria, named by a number of a naming series, which deals with the
		company."""
		number, name = NUMBERED_CUSTOMER
		make_customer(number, "Austria", "ATU87654321", city="Linz", customer_name=name)
		deals_with("Customer", number, COMPANY)
		return number

	def test_the_worklist_names_each_partner_with_its_name_and_finds_it_by_name_or_number(self):
		"""A bookkeeper does not know who „10042“ is: the worklist shows the name beside the ID, and its filter
		finds a partner by either."""
		number = self.numbered_customer()
		columns, rows, _message = worklist_report.execute({"company": COMPANY})
		(column,) = [column for column in columns if column["fieldname"] == "party_name"]
		self.assertEqual(column["fieldtype"], "Data")
		(row,) = [row for row in rows if row["party"] == number]
		self.assertEqual(row["party_name"], "Muster GmbH")
		self.assertEqual(
			[row["party_name"] for row in rows if row["party"] == ALPEN], [ALPEN], "named by its name"
		)
		for search in ("muster", "10042", "Muster GmbH"):
			with self.subTest(search=search):
				_columns, found, _message = worklist_report.execute({"company": COMPANY, "party": search})
				self.assertEqual([row["party"] for row in found], [number])

	def test_a_confirmation_keeps_the_name_of_its_partner_and_follows_a_new_name(self):
		"""The list of all confirmations shows and filters the partner by its name, which the record keeps beside the
		ID and takes over when the partner gets a new name."""
		number = self.numbered_customer()
		name = self.stored(AUSTRIAN, noon(), party=("Customer", number))
		self.assertEqual(frappe.db.get_value(CONFIRMATION, name, "party_name"), "Muster GmbH")
		customer = frappe.get_doc("Customer", number)
		customer._doc_before_save = frappe.get_doc("Customer", number)
		customer.customer_name = "Muster Handel GmbH"
		with patch("frappe.enqueue"):
			partner_module.on_party_update(customer)
		self.assertEqual(frappe.db.get_value(CONFIRMATION, name, "party_name"), "Muster Handel GmbH")

	def test_the_gate_of_an_invoice_names_the_customer_by_its_name_and_its_number(self):
		number = self.numbered_customer()
		doc = self.invoice(number, self.accounts["8125"], customer_name="Muster GmbH")
		with self.assertRaisesRegex(frappe.ValidationError, r"Muster GmbH \(10042\)"):
			partner_module.check_invoice(doc)

	def test_the_worklist_names_german_partners_not_checked_where_the_company_checks_them(self):
		_columns, rows, _message = worklist_report.execute({"company": COMPANY})
		self.assertNotIn(MUENCHEN, [row["party"] for row in rows])
		self.assertIn((PRUEFZIFFER, "Malformed"), [(row["party"], row["standing"]) for row in rows])
		frappe.db.set_value(SETTINGS, COMPANY, "vat_id_check_german", 1)
		_columns, rows, _message = worklist_report.execute({"company": COMPANY})
		self.assertIn(
			(MUENCHEN, "German VAT ID, Not Checked"), [(row["party"], row["standing"]) for row in rows]
		)

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
					(PRUEFZIFFER, "Malformed"),
					(NOWHERE, "Missing"),
					(ZUERICH, "Not Confirmable"),
					(ROMA, "Missing"),
				]
			),
		)
		self.assertEqual(
			[column["fieldname"] for column in columns][:5],
			["party_type", "party", "party_name", "tax_id", "standing"],
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
		for doctype, fieldname, _label in vat_id_setup.LABELLED_FIELDS:
			frappe.db.delete(
				"Property Setter", {"doc_type": doctype, "field_name": fieldname, "property": "label"}
			)
		self.addCleanup(self.forget_labels)
		result = vat_id_setup.check_tax_id_label(context)
		self.assertEqual(
			(result.outcome, result.action.method),
			(Outcome.UNDECIDED, f"{vat_id_setup.__name__}.relabel_tax_id"),
		)
		vat_id_setup.relabel_tax_id()
		self.assertEqual(frappe.get_meta("Customer").get_label("tax_id"), "VAT ID")
		self.assertEqual(
			{
				(doctype, fieldname): frappe.get_meta(doctype).get_label(fieldname)
				for doctype, fieldname in (
					("Sales Invoice", "tax_id"),
					("Sales Invoice", "company_tax_id"),
					("Purchase Invoice", "tax_id"),
					("Sales Order", "tax_id"),
					("Delivery Note", "tax_id"),
				)
			},
			{
				("Sales Invoice", "tax_id"): "VAT ID",
				("Sales Invoice", "company_tax_id"): "Own VAT ID",
				("Purchase Invoice", "tax_id"): "VAT ID",
				("Sales Order", "tax_id"): "VAT ID",
				("Delivery Note", "tax_id"): "VAT ID",
			},
			"the copies of the USt-IdNr. on the documents read as on the partner",
		)
		self.assertEqual(vat_id_setup.check_tax_id_label(context).outcome, Outcome.SKIPPED)

	def forget_labels(self):
		"""Undo the Property Setters before the cache of the DocTypes is cleared, so that it does not keep them."""
		frappe.db.rollback(save_point="partner_vat_id_test")
		for doctype, _fieldname, _label in vat_id_setup.LABELLED_FIELDS:
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
			[step["key"] for step in frappe.get_hooks("steuerbote_setup_steps", app_name="steuerbote")][-4:],
			["vat_id_label", "erpnext_germany_vat_id_check", "vat_id_automatic_check", "eric_settings"],
		)
