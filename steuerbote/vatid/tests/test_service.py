"""When a confirmation asks the BZSt, when it asks again with name and address, and when VIES answers."""

import json
from unittest import TestCase

from steuerbote.vatid import bzst, vies
from steuerbote.vatid.bzst import STATUSES
from steuerbote.vatid.result import Match, Outcome, Service
from steuerbote.vatid.service import confirm
from steuerbote.vatid.tests.fakes import (
	DETAILS,
	REQUESTED,
	REQUESTER,
	FakeClock,
	FakeFetch,
	vies_fault,
)
from steuerbote.vatid.tests.fakes import bzst as bzst_answer
from steuerbote.vatid.tests.fakes import vies as vies_answer
from steuerbote.vatid.transport import Response

UNAVAILABLE = [code for code, status in STATUSES.items() if status.unavailable]
ANSWERED = [code for code, status in STATUSES.items() if not status.unavailable]


def run(*answers, details=None, requested=REQUESTED, requester=REQUESTER):
	fetch = FakeFetch(*answers)
	return confirm(requested, requester, details, fetch, FakeClock()), fetch


class SimpleConfirmationTest(TestCase):
	def test_asks_the_bzst_once(self):
		record, fetch = run(bzst_answer("evatr-0000"))
		self.assertEqual(fetch.urls(), [bzst.URL])
		self.assertEqual(
			(record.service, record.outcome, record.status), (Service.BZST, Outcome.VALID, "evatr-0000")
		)
		self.assertEqual((record.previous, record.fallback_reason), (None, None))
		self.assertEqual(record.queries(), (record,))

	def test_never_asks_vies_after_an_answer_of_the_bzst(self):
		for code in ANSWERED:
			with self.subTest(status=code):
				record, fetch = run(bzst_answer(code, STATUSES[code].http or 200))
				self.assertEqual(fetch.urls(), [bzst.URL])
				self.assertEqual((record.service, record.status), (Service.BZST, code))

	def test_never_asks_vies_after_an_unreadable_answer_without_a_server_error(self):
		for response in (
			Response(200, b"<html/>"),
			Response(403, b"Forbidden"),
			bzst_answer("evatr-9999", 400),
		):
			with self.subTest(response=response):
				record, fetch = run(response)
				self.assertEqual(fetch.urls(), [bzst.URL])
				self.assertIs(record.outcome, Outcome.UNKNOWN)

	def test_reads_the_numbers_in_any_form(self):
		record, fetch = run(bzst_answer("evatr-0000"), requested="atu 123 456 78", requester="de 123.456.789")
		self.assertEqual((record.requested, record.requester), (REQUESTED, REQUESTER))
		self.assertEqual(json.loads(fetch.requests[0].body)["angefragteUstid"], REQUESTED)

	def test_refuses_numbers_without_asking_anyone(self):
		for requested, requester in (
			("DE987654321", REQUESTER),
			(REQUESTED, "ATU12345678"),
			(None, REQUESTER),
		):
			fetch = FakeFetch()
			with self.subTest(requested=requested, requester=requester), self.assertRaises(ValueError):
				confirm(requested, requester, None, fetch, FakeClock())
			self.assertEqual(fetch.requests, [])


class QualifiedConfirmationTest(TestCase):
	def test_follows_the_simple_query_once_the_bzst_confirmed_the_number(self):
		record, fetch = run(
			bzst_answer("evatr-0000"),
			bzst_answer("evatr-0000", ergFirmenname="A", ergStrasse="A", ergPlz="A", ergOrt="A"),
			details=DETAILS,
		)
		self.assertEqual(fetch.urls(), [bzst.URL, bzst.URL])
		simple, qualified = (json.loads(request.body) for request in fetch.requests)
		self.assertNotIn("firmenname", simple)
		self.assertEqual(qualified["firmenname"], "Musterhaus GmbH & Co KG")
		self.assertEqual(
			(record.service, record.outcome, record.details), (Service.BZST, Outcome.VALID, DETAILS)
		)
		self.assertEqual(record.name_match, Match.MATCHES)
		self.assertEqual([query.qualified for query in record.queries()], [False, True])
		self.assertIs(record.previous.outcome, Outcome.VALID)

	def test_is_not_asked_for_a_number_the_bzst_did_not_confirm(self):
		for code in ("evatr-2001", "evatr-0004", "evatr-0012"):
			with self.subTest(status=code):
				record, fetch = run(bzst_answer(code, STATUSES[code].http), details=DETAILS)
				self.assertEqual(fetch.urls(), [bzst.URL])
				self.assertIsNone(record.details)
				self.assertIsNone(record.previous)

	def test_a_qualified_query_the_bzst_cannot_answer_does_not_go_to_vies(self):
		record, fetch = run(bzst_answer("evatr-0000"), bzst_answer("evatr-1001", 503), details=DETAILS)
		self.assertEqual(fetch.urls(), [bzst.URL, bzst.URL])
		self.assertEqual(
			(record.service, record.outcome, record.unavailable), (Service.BZST, Outcome.UNKNOWN, True)
		)
		self.assertTrue(record.qualified)
		self.assertIs(record.previous.outcome, Outcome.VALID)


class FallbackTest(TestCase):
	def test_asks_vies_when_the_bzst_cannot_answer(self):
		failures = [
			TimeoutError("timed out"),
			Response(502, b"<html><body>Bad Gateway</body></html>"),
			bzst_answer("evatr-9999", 500),
			*(bzst_answer(code, STATUSES[code].http) for code in UNAVAILABLE),
		]
		for failure in failures:
			with self.subTest(failure=failure):
				record, fetch = run(failure, vies_answer())
				self.assertEqual(fetch.urls(), [bzst.URL, vies.URL])
				self.assertEqual((record.service, record.outcome), (Service.VIES, Outcome.VALID))
				self.assertIs(record.previous.service, Service.BZST)
				self.assertTrue(record.previous.unavailable)
				self.assertEqual(
					record.fallback_reason,
					f"Das BZSt konnte die Anfrage nicht beantworten ({record.previous.status}): "
					f"{record.previous.message}",
				)

	def test_every_status_the_catalogue_gives_a_server_error_goes_to_vies(self):
		self.assertEqual(len(UNAVAILABLE), 10)

	def test_vies_gets_name_and_address_when_it_answers_in_place_of_the_bzst(self):
		record, fetch = run(
			bzst_answer("evatr-1001", 503),
			vies_answer(
				traderNameMatch="1", traderStreetMatch="1", traderPostcodeMatch="1", traderCityMatch="2"
			),
			details=DETAILS,
		)
		self.assertEqual(fetch.urls(), [bzst.URL, vies.URL])
		self.assertIn(b"<v:traderName>Musterhaus GmbH &amp; Co KG</v:traderName>", fetch.requests[1].body)
		self.assertEqual((record.details, record.city_match), (DETAILS, Match.DIFFERS))
		self.assertIsNone(record.previous.details)

	def test_an_unavailable_vies_leaves_the_outcome_unknown(self):
		record, fetch = run(bzst_answer("evatr-1001", 503), vies_fault("MS_UNAVAILABLE"))
		self.assertEqual(fetch.urls(), [bzst.URL, vies.URL])
		self.assertEqual(
			(record.service, record.outcome, record.status, record.unavailable),
			(Service.VIES, Outcome.UNKNOWN, "MS_UNAVAILABLE", True),
		)
		self.assertEqual(record.queries(), (record.previous, record))

	def test_the_fallback_reason_names_the_answer_of_the_bzst(self):
		record, _ = run(bzst_answer("evatr-1001", 503), vies_answer(valid=False))
		self.assertEqual(
			record.fallback_reason,
			"Das BZSt konnte die Anfrage nicht beantworten (evatr-1001): Eine Bearbeitung Ihrer Anfrage ist "
			"zurzeit nicht möglich. Bitte versuchen Sie es später noch einmal.",
		)
		self.assertIs(record.outcome, Outcome.INVALID)
