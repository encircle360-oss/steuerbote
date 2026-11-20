"""The query to VIES with checkVatApprox, against a fake transport."""

from datetime import date, timedelta
from unittest import TestCase

from lxml import etree

from steuerbote.vatid import vies
from steuerbote.vatid.result import NO_ANSWER, UNREADABLE, Details, Match, Outcome, Service
from steuerbote.vatid.tests.fakes import (
	DETAILS,
	REQUESTED,
	REQUESTER,
	START,
	VIES_IDENTIFIER,
	FakeClock,
	FakeFetch,
	vies_fault,
)
from steuerbote.vatid.tests.fakes import vies as answer
from steuerbote.vatid.transport import Response
from steuerbote.vatid.vies import FAULTS, URL

SOAP = "{http://schemas.xmlsoap.org/soap/envelope/}"
TYPES = "{urn:ec.europa.eu:taxud:vies:services:checkVat:types}"
DOCUMENTED_FAULTS = {
	"INVALID_INPUT",
	"GLOBAL_MAX_CONCURRENT_REQ",
	"MS_MAX_CONCURRENT_REQ",
	"SERVICE_UNAVAILABLE",
	"MS_UNAVAILABLE",
	"TIMEOUT",
}


def query(*answers, details=None, requested=REQUESTED, requester=REQUESTER):
	fetch = FakeFetch(*answers)
	return vies.query(requested, requester, details, fetch, FakeClock()), fetch


def sent(fetch: FakeFetch) -> list[tuple[str, str]]:
	"""The elements of checkVatApprox in the request, as local name and text."""
	root = etree.fromstring(fetch.requests[0].body)
	check = root.find(f"{SOAP}Body/{TYPES}checkVatApprox")
	return [(etree.QName(child).localname, child.text) for child in check]


class RequestTest(TestCase):
	def test_posts_check_vat_approx_with_the_requester(self):
		_, fetch = query(answer())
		(request,) = fetch.requests
		self.assertEqual(request.url, "https://ec.europa.eu/taxation_customs/vies/services/checkVatService")
		self.assertEqual(URL, request.url)
		self.assertEqual(
			dict(request.headers), {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'}
		)
		self.assertTrue(request.body.startswith(b"<?xml version='1.0' encoding='UTF-8'?>"))
		self.assertEqual(
			sent(fetch),
			[
				("countryCode", "AT"),
				("vatNumber", "U12345678"),
				("requesterCountryCode", "DE"),
				("requesterVatNumber", "123456789"),
			],
		)

	def test_adds_name_and_address_in_the_order_of_the_wsdl(self):
		_, fetch = query(answer(), details=DETAILS)
		self.assertEqual(
			sent(fetch),
			[
				("countryCode", "AT"),
				("vatNumber", "U12345678"),
				("traderName", "Musterhaus GmbH & Co KG"),
				("traderStreet", "Musterstrasse 22"),
				("traderPostcode", "12345"),
				("traderCity", "musterort"),
				("requesterCountryCode", "DE"),
				("requesterVatNumber", "123456789"),
			],
		)
		self.assertIn(b"Musterhaus GmbH &amp; Co KG", fetch.requests[0].body)

	def test_leaves_out_what_is_not_known_of_the_address(self):
		_, fetch = query(answer(), details=Details("Musterhaus GmbH & Co KG", "musterort"))
		self.assertEqual(
			[name for name, _ in sent(fetch)],
			[
				"countryCode",
				"vatNumber",
				"traderName",
				"traderCity",
				"requesterCountryCode",
				"requesterVatNumber",
			],
		)

	def test_sends_the_country_code_of_the_number(self):
		for requested, code, number in (("el 123 456 789", "EL", "123456789"), ("XIGD123", "XI", "GD123")):
			with self.subTest(requested=requested):
				_, fetch = query(answer(), requested=requested)
				self.assertEqual(sent(fetch)[:2], [("countryCode", code), ("vatNumber", number)])

	def test_refuses_numbers_it_would_not_ask_about_without_sending_anything(self):
		for requested, requester in (("DE123456789", REQUESTER), (REQUESTED, "ATU12345678")):
			fetch = FakeFetch()
			with self.subTest(requested=requested, requester=requester), self.assertRaises(ValueError):
				vies.query(requested, requester, None, fetch, FakeClock())
			self.assertEqual(fetch.requests, [])


class AnswerTest(TestCase):
	def test_keeps_a_valid_answer_with_its_request_identifier(self):
		response = answer()
		record, _ = query(response)
		self.assertEqual(
			(record.requested, record.requester, record.service, record.outcome, record.status),
			(REQUESTED, REQUESTER, Service.VIES, Outcome.VALID, "VALID"),
		)
		self.assertEqual(record.message, "Laut VIES ist die USt-IdNr. zum Zeitpunkt der Anfrage gültig.")
		self.assertEqual(record.consultation_id, VIES_IDENTIFIER)
		self.assertEqual((record.service_date, record.service_time), (date(2026, 11, 20), None))
		self.assertEqual((record.requested_at, record.answered_at), (START, START + timedelta(seconds=1)))
		self.assertEqual((record.http_status, record.response_text), (200, response.body.decode()))
		self.assertFalse(record.unavailable)

	def test_an_invalid_answer(self):
		record, _ = query(answer(valid=False, requestIdentifier=""))
		self.assertEqual((record.outcome, record.status), (Outcome.INVALID, "INVALID"))
		self.assertEqual(
			record.message, "Laut VIES ist die USt-IdNr. zum Zeitpunkt der Anfrage nicht gültig."
		)

	def test_an_empty_request_identifier_is_no_consultation_number(self):
		record, _ = query(answer(requestIdentifier=""))
		self.assertIs(record.outcome, Outcome.VALID)
		self.assertIsNone(record.consultation_id)

	def test_reads_valid_as_xsd_boolean(self):
		for text, outcome in (
			("true", Outcome.VALID),
			("1", Outcome.VALID),
			("false", Outcome.INVALID),
			("0", Outcome.INVALID),
		):
			with self.subTest(text=text):
				self.assertIs(query(answer(valid=text))[0].outcome, outcome)

	def test_reads_the_request_date_with_or_without_time_zone(self):
		for text in ("2026-11-20", "2026-11-20Z", "2026-11-20+01:00", "2026-11-20-05:00"):
			with self.subTest(text=text):
				self.assertEqual(query(answer(requestDate=text))[0].service_date, date(2026, 11, 20))

	def test_reads_the_matches_of_a_qualified_query(self):
		record, _ = query(
			answer(traderNameMatch="1", traderStreetMatch="2", traderPostcodeMatch="3", traderCityMatch="1"),
			details=DETAILS,
		)
		self.assertEqual(record.details, DETAILS)
		self.assertEqual(
			(record.name_match, record.street_match, record.postcode_match, record.city_match),
			(Match.MATCHES, Match.DIFFERS, Match.NOT_PROVIDED, Match.MATCHES),
		)

	def test_a_qualified_answer_without_matches_leaves_them_open(self):
		record, _ = query(answer(), details=DETAILS)
		self.assertEqual((record.name_match, record.city_match), (None, None))

	def test_a_simple_query_has_no_matches(self):
		record, _ = query(answer(traderNameMatch="1"))
		self.assertIsNone(record.name_match)


class FaultTest(TestCase):
	def test_maps_every_fault_the_wsdl_documents(self):
		self.assertEqual(set(FAULTS), DOCUMENTED_FAULTS)
		for code, fault in FAULTS.items():
			with self.subTest(fault=code):
				record, _ = query(vies_fault(code))
				self.assertEqual(
					(record.service, record.outcome, record.status, record.message, record.unavailable),
					(Service.VIES, fault.outcome, code, fault.message, fault.unavailable),
				)
				self.assertEqual(record.http_status, 500)
				self.assertIsNone(record.consultation_id)

	def test_only_invalid_input_says_the_number_is_invalid(self):
		self.assertEqual(
			{code for code, fault in FAULTS.items() if fault.outcome is Outcome.INVALID}, {"INVALID_INPUT"}
		)
		self.assertEqual(
			{code for code, fault in FAULTS.items() if fault.unavailable},
			DOCUMENTED_FAULTS - {"INVALID_INPUT"},
		)
		for fault in FAULTS.values():
			self.assertIs(
				fault.outcome, Outcome.INVALID if fault.code == "INVALID_INPUT" else Outcome.UNKNOWN
			)

	def test_an_undocumented_fault_leaves_the_outcome_unknown(self):
		record, _ = query(vies_fault("INVALID_REQUESTER_INFO"))
		self.assertEqual(
			(record.outcome, record.status, record.unavailable),
			(Outcome.UNKNOWN, "INVALID_REQUESTER_INFO", False),
		)
		self.assertEqual(record.message, "VIES hat mit dem Fehler INVALID_REQUESTER_INFO geantwortet.")

	def test_reads_the_fault_string_without_surrounding_blanks(self):
		record, _ = query(vies_fault(" MS_UNAVAILABLE\n"))
		self.assertEqual(record.status, "MS_UNAVAILABLE")


class NoAnswerTest(TestCase):
	def test_no_answer_at_all_makes_vies_unavailable(self):
		record, _ = query(TimeoutError("timed out"))
		self.assertEqual(
			(record.outcome, record.status, record.unavailable), (Outcome.UNKNOWN, NO_ANSWER, True)
		)
		self.assertEqual(record.message, "Keine Antwort von VIES: timed out.")
		self.assertEqual((record.http_status, record.response_text), (None, None))
		record, _ = query(OSError())
		self.assertEqual(record.message, "Keine Antwort von VIES: OSError.")

	def test_a_server_error_without_a_readable_answer_makes_vies_unavailable(self):
		record, _ = query(Response(503, b"<html><body>Service Unavailable</body></html>"))
		self.assertEqual(
			(record.outcome, record.status, record.unavailable), (Outcome.UNKNOWN, UNREADABLE, True)
		)
		self.assertEqual(
			record.message, "Die Antwort von VIES (HTTP 503) ist nicht lesbar: kein SOAP-Umschlag."
		)

	def test_an_unreadable_answer_without_a_server_error_is_unknown(self):
		envelope = '<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">{}</env:Envelope>'
		cases = (
			(Response(200, b""), "kein XML"),
			(Response(200, b"not xml"), "kein XML"),
			(
				Response(200, b'<!DOCTYPE env [<!ENTITY a "a">]>' + envelope.format("<env:Body/>").encode()),
				"enthält eine DTD",
			),
			(Response(200, b"<Envelope/>"), "kein SOAP-Umschlag"),
			(Response(200, envelope.format("").encode()), "kein SOAP-Body"),
			(Response(200, envelope.format("<env:Body/>").encode()), "weder Antwort noch Fehler"),
			(
				Response(
					200,
					envelope.format(
						"<env:Body><env:Fault><faultcode>env:Server</faultcode></env:Fault></env:Body>"
					).encode(),
				),
				"Fehler ohne faultstring",
			),
			(answer(valid=None), "valid fehlt"),
			(answer(valid="yes"), "valid ist kein Wahrheitswert: 'yes'"),
			(answer(requestDate=None), "requestDate fehlt"),
			(answer(requestDate="20.11.2026"), "requestDate ist kein Datum: '20.11.2026'"),
			(answer(requestDate="2026-02-30"), "requestDate ist kein Datum: '2026-02-30'"),
			(answer(requestIdentifier=None), "requestIdentifier fehlt"),
		)
		for response, reason in cases:
			with self.subTest(reason=reason, body=response.body):
				record, _ = query(response)
				self.assertEqual(
					(record.outcome, record.status, record.unavailable), (Outcome.UNKNOWN, UNREADABLE, False)
				)
				self.assertEqual(
					record.message,
					f"Die Antwort von VIES (HTTP {response.status}) ist nicht lesbar: {reason}.",
				)

	def test_a_match_other_than_one_to_three_makes_the_answer_unreadable(self):
		record, _ = query(answer(traderNameMatch="4"), details=DETAILS)
		self.assertEqual((record.outcome, record.status), (Outcome.UNKNOWN, UNREADABLE))
		self.assertIn("traderNameMatch ist keiner der Werte 1 bis 3: '4'", record.message)

	def test_a_fault_comes_with_a_server_error_and_is_still_read(self):
		record, _ = query(vies_fault("TIMEOUT", http=500))
		self.assertEqual(record.status, "TIMEOUT")
