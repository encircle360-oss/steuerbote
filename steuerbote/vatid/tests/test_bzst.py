"""The query to the eVatR REST API of the BZSt, against a fake transport.

The fixture statusmeldungen.json is the status catalogue of the BZSt,
https://api.evatr.vies.bzst.de/v1/info/statusmeldungen, retrieved on 20 November 2026.
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase

from steuerbote.vatid import bzst
from steuerbote.vatid.bzst import STATUSES, URL
from steuerbote.vatid.result import NO_ANSWER, UNREADABLE, Details, Match, Outcome, Service
from steuerbote.vatid.tests.fakes import (
	BZST_ID,
	BZST_TIME,
	DETAILS,
	REQUESTED,
	REQUESTER,
	START,
	FakeClock,
	FakeFetch,
)
from steuerbote.vatid.tests.fakes import bzst as answer
from steuerbote.vatid.transport import Response

CATALOGUE = json.loads(
	(Path(__file__).resolve().parent / "fixtures" / "statusmeldungen.json").read_text(encoding="utf-8")
)
WINTER_TIME = timezone(timedelta(hours=1))
VALID_CODES = {"evatr-0000", "evatr-0003", "evatr-2008"}
INVALID_CODES = {"evatr-0005", "evatr-0012", "evatr-2001", "evatr-2002", "evatr-2003", "evatr-2006"}
UNAVAILABLE_CODES = {
	"evatr-0011",
	"evatr-0013",
	"evatr-1001",
	"evatr-1002",
	"evatr-1003",
	"evatr-1004",
	"evatr-2004",
	"evatr-2007",
	"evatr-2011",
	"evatr-3011",
}


def query(*answers, details=None, requested=REQUESTED, requester=REQUESTER):
	fetch = FakeFetch(*answers)
	return bzst.query(requested, requester, details, fetch, FakeClock()), fetch


def body(**fields) -> Response:
	return Response(200, json.dumps(fields).encode())


class CatalogueTest(TestCase):
	def test_holds_every_status_of_the_catalogue_word_for_word(self):
		self.assertEqual(len(STATUSES), 26)
		self.assertEqual(list(STATUSES), [entry["status"] for entry in CATALOGUE])
		for entry in CATALOGUE:
			status = STATUSES[entry["status"]]
			with self.subTest(status=status.code):
				self.assertEqual(
					(status.http, status.category, status.field, status.message),
					(entry.get("httpcode"), entry["kategorie"], entry.get("feld"), entry["meldung"]),
				)

	def test_valid_are_the_codes_whose_message_says_so(self):
		valid = {code for code, status in STATUSES.items() if status.outcome is Outcome.VALID}
		self.assertEqual(valid, VALID_CODES)
		for code in valid:
			self.assertIn("ist zum Anfragezeitpunkt gültig.", STATUSES[code].message)

	def test_invalid_are_the_codes_that_say_the_number_is_not_valid_or_malformed(self):
		invalid = {code for code, status in STATUSES.items() if status.outcome is Outcome.INVALID}
		self.assertEqual(invalid, INVALID_CODES)
		for code in invalid:
			self.assertEqual(STATUSES[code].field, "angefragteUstid")

	def test_every_other_code_leaves_the_outcome_unknown(self):
		unknown = {code for code, status in STATUSES.items() if status.outcome is Outcome.UNKNOWN}
		self.assertEqual(unknown, set(STATUSES) - VALID_CODES - INVALID_CODES)

	def test_the_bzst_is_unavailable_with_the_codes_the_catalogue_gives_a_server_error(self):
		unavailable = {code for code, status in STATUSES.items() if status.unavailable}
		self.assertEqual(unavailable, UNAVAILABLE_CODES)
		for code in unavailable:
			self.assertIn(STATUSES[code].http, (500, 503))
			self.assertIs(STATUSES[code].outcome, Outcome.UNKNOWN)


class RequestTest(TestCase):
	def test_posts_the_simple_query_as_json(self):
		_, fetch = query(answer("evatr-0000"))
		(request,) = fetch.requests
		self.assertEqual(request.url, "https://api.evatr.vies.bzst.de/app/v1/abfrage")
		self.assertEqual(URL, request.url)
		self.assertEqual(
			dict(request.headers), {"Content-Type": "application/json", "Accept": "application/json"}
		)
		self.assertEqual(
			json.loads(request.body), {"anfragendeUstid": "DE123456789", "angefragteUstid": "ATU12345678"}
		)

	def test_posts_the_qualified_query_of_the_documentation(self):
		_, fetch = query(answer("evatr-0000"), details=DETAILS)
		self.assertEqual(
			json.loads(fetch.requests[0].body),
			{
				"anfragendeUstid": "DE123456789",
				"angefragteUstid": "ATU12345678",
				"firmenname": "Musterhaus GmbH & Co KG",
				"strasse": "Musterstrasse 22",
				"plz": "12345",
				"ort": "musterort",
			},
		)

	def test_leaves_out_street_and_postcode_when_they_are_not_known(self):
		_, fetch = query(answer("evatr-0000"), details=Details("Musterhaus GmbH & Co KG", "musterort"))
		self.assertEqual(
			json.loads(fetch.requests[0].body),
			{
				"anfragendeUstid": "DE123456789",
				"angefragteUstid": "ATU12345678",
				"firmenname": "Musterhaus GmbH & Co KG",
				"ort": "musterort",
			},
		)

	def test_sends_utf_8(self):
		_, fetch = query(answer("evatr-0000"), details=Details("Bäckerei Müller GmbH", "Graz"))
		self.assertIn("Bäckerei Müller GmbH".encode(), fetch.requests[0].body)

	def test_sends_both_numbers_normalized(self):
		_, fetch = query(answer("evatr-0000"), requested="atu 123 456 78", requester="de 123.456.789")
		sent = json.loads(fetch.requests[0].body)
		self.assertEqual((sent["anfragendeUstid"], sent["angefragteUstid"]), ("DE123456789", "ATU12345678"))

	def test_refuses_numbers_it_would_not_ask_about_without_sending_anything(self):
		for requested, requester in (
			("DE123456789", REQUESTER),
			("GB123456789", REQUESTER),
			("ATU123", REQUESTER),
			(REQUESTED, "ATU12345678"),
			(REQUESTED, "DE12345678"),
		):
			fetch = FakeFetch()
			with self.subTest(requested=requested, requester=requester), self.assertRaises(ValueError):
				bzst.query(requested, requester, None, fetch, FakeClock())
			self.assertEqual(fetch.requests, [])


class AnswerTest(TestCase):
	def test_keeps_a_valid_answer_with_what_was_asked(self):
		response = answer("evatr-0000")
		record, _ = query(response)
		self.assertEqual(
			(record.requested, record.requester, record.service, record.outcome, record.status),
			(REQUESTED, REQUESTER, Service.BZST, Outcome.VALID, "evatr-0000"),
		)
		self.assertEqual(record.message, "Die angefragte USt-IdNr. ist zum Anfragezeitpunkt gültig.")
		self.assertEqual(record.consultation_id, BZST_ID)
		self.assertEqual(record.service_time, datetime(2026, 11, 20, 15, 0, 0, 123456, tzinfo=WINTER_TIME))
		self.assertEqual(record.service_date, date(2026, 11, 20))
		self.assertEqual((record.requested_at, record.answered_at), (START, START + timedelta(seconds=1)))
		self.assertEqual((record.http_status, record.response_text), (200, response.body.decode()))
		self.assertIn(BZST_TIME, record.response_text)
		self.assertFalse(record.unavailable)
		self.assertIsNone(record.details)
		self.assertIsNone(record.previous)
		self.assertIsNone(record.fallback_reason)

	def test_reads_every_status_of_the_catalogue(self):
		for code, status in STATUSES.items():
			with self.subTest(status=code):
				record, _ = query(answer(code, status.http or 200))
				self.assertEqual(
					(record.status, record.outcome, record.message, record.unavailable),
					(code, status.outcome, status.message, status.unavailable),
				)
				self.assertEqual(record.http_status, status.http or 200)

	def test_keeps_the_validity_dates(self):
		record, _ = query(answer("evatr-2006", gueltigAb="2020-01-01", gueltigBis="2025-12-31"))
		self.assertIs(record.outcome, Outcome.INVALID)
		self.assertEqual((record.valid_from, record.valid_until), (date(2020, 1, 1), date(2025, 12, 31)))
		record, _ = query(answer("evatr-2002", gueltigAb="2027-01-01T00:00:00+01:00"))
		self.assertEqual((record.valid_from, record.valid_until), (date(2027, 1, 1), None))

	def test_reads_the_results_of_the_qualified_query(self):
		record, _ = query(
			answer("evatr-0000", ergFirmenname="A", ergStrasse="B", ergPlz="C", ergOrt="D"), details=DETAILS
		)
		self.assertTrue(record.qualified)
		self.assertEqual(record.details, DETAILS)
		self.assertEqual(
			(record.name_match, record.street_match, record.postcode_match, record.city_match),
			(Match.MATCHES, Match.DIFFERS, Match.NOT_REQUESTED, Match.NOT_PROVIDED),
		)

	def test_a_qualified_answer_without_results_leaves_them_open(self):
		record, _ = query(answer("evatr-2001", 404), details=DETAILS)
		self.assertIs(record.outcome, Outcome.INVALID)
		self.assertEqual(
			(record.name_match, record.street_match, record.postcode_match, record.city_match),
			(None, None, None, None),
		)

	def test_a_simple_query_has_no_results(self):
		record, _ = query(answer("evatr-0000", ergFirmenname="A"))
		self.assertIsNone(record.name_match)

	def test_reads_a_refused_query_in_the_shape_of_the_probe(self):
		record, _ = query(
			Response(
				400,
				b'{"id":"9f8e7d6c5b4a3921","anfrageZeitpunkt":"2026-11-20T15:35:59.960171228+01:00",'
				b'"status":"evatr-0004"}',
			)
		)
		self.assertEqual(
			(record.outcome, record.status, record.unavailable), (Outcome.UNKNOWN, "evatr-0004", False)
		)
		self.assertEqual(record.consultation_id, "9f8e7d6c5b4a3921")
		self.assertEqual(record.service_time, datetime(2026, 11, 20, 15, 35, 59, 960171, tzinfo=WINTER_TIME))

	def test_needs_no_id_and_reads_null_as_missing(self):
		record, _ = query(body(anfrageZeitpunkt=BZST_TIME, status="evatr-0000"))
		self.assertIsNone(record.consultation_id)
		record, _ = query(answer("evatr-2006", id=None, gueltigAb=None, gueltigBis=None))
		self.assertEqual((record.consultation_id, record.valid_from, record.valid_until), (None, None, None))

	def test_an_unknown_status_leaves_the_outcome_unknown(self):
		record, _ = query(answer("evatr-9999"))
		self.assertEqual(
			(record.outcome, record.status, record.unavailable), (Outcome.UNKNOWN, "evatr-9999", False)
		)
		self.assertEqual(
			record.message,
			"Das BZSt hat mit dem Status evatr-9999 geantwortet, den sein Katalog nicht kennt.",
		)
		record, _ = query(answer("evatr-9999", 500))
		self.assertTrue(record.unavailable)


class NoAnswerTest(TestCase):
	def test_no_answer_at_all_makes_the_bzst_unavailable(self):
		for error, reason in (
			(TimeoutError("timed out"), "timed out"),
			(ConnectionRefusedError(111, "Connection refused"), "[Errno 111] Connection refused"),
			(OSError(), "OSError"),
		):
			with self.subTest(error=error):
				record, _ = query(error)
				self.assertEqual(
					(record.outcome, record.status, record.unavailable), (Outcome.UNKNOWN, NO_ANSWER, True)
				)
				self.assertEqual(record.message, f"Keine Antwort vom BZSt: {reason}.")
				self.assertEqual((record.http_status, record.response_text), (None, None))
				self.assertEqual(
					(record.requested_at, record.answered_at), (START, START + timedelta(seconds=1))
				)

	def test_a_server_error_without_a_readable_answer_makes_the_bzst_unavailable(self):
		record, _ = query(Response(502, b"<html><body>Bad Gateway</body></html>"))
		self.assertEqual(
			(record.outcome, record.status, record.unavailable), (Outcome.UNKNOWN, UNREADABLE, True)
		)
		self.assertEqual(
			record.message, "Die Antwort des BZSt (HTTP 502) ist nicht lesbar: kein JSON in UTF-8."
		)
		self.assertEqual(
			(record.http_status, record.response_text), (502, "<html><body>Bad Gateway</body></html>")
		)

	def test_an_unreadable_answer_without_a_server_error_is_unknown(self):
		cases = (
			(Response(200, b"<html></html>"), "kein JSON in UTF-8"),
			(Response(200, b"\xff\xfe{}"), "kein JSON in UTF-8"),
			(Response(403, b"Forbidden"), "kein JSON in UTF-8"),
			(Response(200, b"[]"), "kein JSON-Objekt"),
			(body(anfrageZeitpunkt=BZST_TIME), "status fehlt"),
			(body(anfrageZeitpunkt=BZST_TIME, status=""), "status fehlt"),
			(body(anfrageZeitpunkt=BZST_TIME, status=0), "status ist kein Text"),
			(body(status="evatr-0000"), "anfrageZeitpunkt fehlt"),
			(
				body(anfrageZeitpunkt="gestern", status="evatr-0000"),
				"anfrageZeitpunkt ist kein Zeitpunkt: 'gestern'",
			),
			(body(anfrageZeitpunkt=1795701600, status="evatr-0000"), "anfrageZeitpunkt ist kein Text"),
			(answer("evatr-0000", id=17), "id ist kein Text"),
			(answer("evatr-2006", gueltigAb="01.01.2020"), "gueltigAb ist kein Datum: '01.01.2020'"),
		)
		for response, reason in cases:
			with self.subTest(reason=reason, body=response.body):
				record, _ = query(response)
				self.assertEqual(
					(record.outcome, record.status, record.unavailable), (Outcome.UNKNOWN, UNREADABLE, False)
				)
				self.assertEqual(
					record.message,
					f"Die Antwort des BZSt (HTTP {response.status}) ist nicht lesbar: {reason}.",
				)

	def test_a_result_other_than_a_to_d_makes_the_answer_unreadable(self):
		record, _ = query(answer("evatr-0000", ergFirmenname="E"), details=DETAILS)
		self.assertEqual((record.outcome, record.status), (Outcome.UNKNOWN, UNREADABLE))
		self.assertIn("ergFirmenname ist keiner der Buchstaben A bis D: 'E'", record.message)

	def test_keeps_an_unreadable_answer_as_far_as_it_is_text(self):
		record, _ = query(Response(200, b"\xff\xfe{}"))
		self.assertEqual(record.response_text, "��{}")
