"""Each query of a confirmation becomes a record of its own, with what was asked, what came back and what the
confirmation says of the number up to it."""

from datetime import UTC, date, datetime
from unittest import TestCase

from steuerbote.steuerbote.doctype.vat_id_confirmation import records
from steuerbote.vatid.result import Outcome
from steuerbote.vatid.service import confirm
from steuerbote.vatid.tests.fakes import (
	BZST_ID,
	DETAILS,
	REQUESTED,
	REQUESTER,
	START,
	VIES_IDENTIFIER,
	FakeClock,
	FakeFetch,
	bzst,
	vies,
)
from steuerbote.vatid.transport import Response


def confirmed(*answers, details=None):
	return confirm(REQUESTED, REQUESTER, details, FakeFetch(*answers), FakeClock())


class RecordsTest(TestCase):
	def test_a_simple_query_is_one_record_with_its_answer(self):
		(record,) = records.records(confirmed(bzst("evatr-0000")))
		self.assertEqual(
			record,
			{
				"requested": REQUESTED,
				"requester": REQUESTER,
				"service": "bzst",
				"outcome": "valid",
				"result": "valid",
				"status_code": "evatr-0000",
				"message": "Die angefragte USt-IdNr. ist zum Anfragezeitpunkt gültig.",
				"consultation_id": BZST_ID,
				"requested_at": START,
				"answered_at": datetime(2026, 11, 20, 14, 0, 1, tzinfo=UTC),
				"service_time": datetime.fromisoformat("2026-11-20T15:00:00.123456+01:00"),
				"service_date": date(2026, 11, 20),
				"valid_from": None,
				"valid_until": None,
				"qualified": 0,
				"details_name": None,
				"details_street": None,
				"details_postcode": None,
				"details_city": None,
				"name_match": None,
				"street_match": None,
				"postcode_match": None,
				"city_match": None,
				"http_status": 200,
				"unavailable": 0,
				"fallback_reason": None,
			},
		)

	def test_the_qualified_query_follows_with_name_address_and_its_results(self):
		simple, qualified = records.records(
			confirmed(
				bzst("evatr-0000"),
				bzst("evatr-0000", ergFirmenname="A", ergStrasse="B", ergPlz="A", ergOrt="D"),
				details=DETAILS,
			)
		)
		self.assertEqual((simple["qualified"], simple["details_name"], simple["name_match"]), (0, None, None))
		self.assertEqual(
			{key: qualified[key] for key in records.DETAILS_FIELDS},
			{
				"details_name": "Musterhaus GmbH & Co KG",
				"details_street": "Musterstrasse 22",
				"details_postcode": "12345",
				"details_city": "musterort",
			},
		)
		self.assertEqual(
			[
				qualified[key]
				for key in ("qualified", "name_match", "street_match", "postcode_match", "city_match")
			],
			[1, "A", "B", "A", "D"],
		)

	def test_a_failed_qualified_query_leaves_the_number_confirmed(self):
		simple, qualified = records.records(
			confirmed(bzst("evatr-0000"), OSError("timed out"), details=DETAILS)
		)
		self.assertEqual(
			(simple["result"], qualified["outcome"], qualified["result"]), ("valid", "unknown", "valid")
		)
		self.assertEqual((qualified["unavailable"], qualified["http_status"]), (1, None))

	def test_vies_answers_when_the_bzst_cannot_and_says_why(self):
		bzst_record, vies_record = records.records(confirmed(bzst("evatr-1001", 503), vies(valid=False)))
		self.assertEqual(
			[
				(record["service"], record["outcome"], record["result"])
				for record in (bzst_record, vies_record)
			],
			[("bzst", "unknown", "unknown"), ("vies", "invalid", "invalid")],
		)
		self.assertEqual(vies_record["consultation_id"], VIES_IDENTIFIER)
		self.assertTrue(
			vies_record["fallback_reason"].startswith(
				"Das BZSt konnte die Anfrage nicht beantworten (evatr-1001)"
			)
		)

	def test_validity_dates_of_a_number_no_longer_valid(self):
		(record,) = records.records(
			confirmed(bzst("evatr-2006", gueltigAb="2020-01-01", gueltigBis="2025-06-30"))
		)
		self.assertEqual(
			(record["outcome"], record["valid_from"], record["valid_until"]),
			("invalid", date(2020, 1, 1), date(2025, 6, 30)),
		)


class ResultTest(TestCase):
	def test_the_outcome_of_the_last_query_that_has_one(self):
		valid, unknown, invalid = (
			confirmed(bzst("evatr-0000")),
			confirmed(OSError("no route"), Response(500, b"")),
			confirmed(bzst("evatr-2001", 404)),
		)
		self.assertIs(records.result([valid]), Outcome.VALID)
		self.assertIs(records.result([valid, *unknown.queries()]), Outcome.VALID)
		self.assertIs(records.result(unknown.queries()), Outcome.UNKNOWN)
		self.assertIs(records.result([valid, invalid]), Outcome.INVALID)
		self.assertIs(records.result([]), Outcome.UNKNOWN)


class ResponseFileTest(TestCase):
	def test_the_bzst_answers_json_and_vies_xml(self):
		bzst_query, vies_query = confirmed(bzst("evatr-1001", 503), vies()).queries()
		self.assertEqual(
			records.response_file_name("USTID-2026-00001", bzst_query), "USTID-2026-00001-bzst.json"
		)
		self.assertEqual(
			records.response_file_name("USTID-2026-00002", vies_query), "USTID-2026-00002-vies.xml"
		)
