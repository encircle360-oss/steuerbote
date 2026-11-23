from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from unittest import TestCase

from steuerbote.vatid.result import Confirmation, Details, Match, Outcome, Service, valid_through

BERLIN_WINTER = timezone(timedelta(hours=1))
ASKED = datetime(2026, 11, 20, 14, 0, 0, tzinfo=UTC)


def confirmation(**changes) -> Confirmation:
	fields = {
		"requested": "ATU12345678",
		"requester": "DE123456789",
		"service": Service.BZST,
		"outcome": Outcome.VALID,
		"status": "evatr-0000",
		"message": "Die angefragte USt-IdNr. ist zum Anfragezeitpunkt gültig.",
		"requested_at": ASKED,
		"answered_at": ASKED + timedelta(seconds=1),
		"consultation_id": "0a1b2c3d4e5f6071",
		"service_time": datetime(2026, 11, 20, 15, 0, 0, tzinfo=BERLIN_WINTER),
		"service_date": date(2026, 11, 20),
		"http_status": 200,
		"response_text": '{"status":"evatr-0000"}',
	}
	return Confirmation(**(fields | changes))


class EnumTest(TestCase):
	def test_services_are_the_bzst_and_vies(self):
		self.assertEqual([service.value for service in Service], ["bzst", "vies"])

	def test_outcomes_are_valid_invalid_and_unknown(self):
		self.assertEqual([outcome.value for outcome in Outcome], ["valid", "invalid", "unknown"])

	def test_matches_carry_the_letters_of_the_bzst(self):
		self.assertEqual([match.value for match in Match], ["A", "B", "C", "D"])


class DetailsTest(TestCase):
	def test_keeps_name_and_address_without_surrounding_blanks(self):
		details = Details(" Musterhaus GmbH & Co KG ", "musterort ", "12345 ", " Musterstrasse 22")
		self.assertEqual(
			(details.name, details.city, details.postcode, details.street),
			("Musterhaus GmbH & Co KG", "musterort", "12345", "Musterstrasse 22"),
		)

	def test_postcode_and_street_are_optional(self):
		details = Details("Musterhaus GmbH & Co KG", "musterort")
		self.assertEqual((details.postcode, details.street), ("", ""))

	def test_needs_the_name_and_the_city(self):
		for name, city in (("", "musterort"), ("Musterhaus GmbH", " "), ("  ", "")):
			with self.subTest(name=name, city=city), self.assertRaises(ValueError):
				Details(name, city)

	def test_refuses_control_characters(self):
		with self.assertRaises(ValueError):
			Details("Musterhaus\x0bGmbH", "musterort")
		with self.assertRaises(ValueError):
			Details("Musterhaus GmbH", "musterort", street="Musterstrasse\x0022")

	def test_refuses_what_is_not_text(self):
		with self.assertRaises(TypeError):
			Details("Musterhaus GmbH", None)


class ConfirmationTest(TestCase):
	def test_times_of_the_clock_carry_a_time_zone(self):
		with self.assertRaises(ValueError):
			confirmation(requested_at=datetime(2026, 11, 20, 14, 0))
		with self.assertRaises(ValueError):
			confirmation(answered_at=datetime(2026, 11, 20, 14, 0))

	def test_the_service_date_is_the_day_of_the_service_time(self):
		with self.assertRaises(ValueError):
			confirmation(service_date=date(2026, 11, 21))
		self.assertEqual(
			confirmation(service_time=None, service_date=date(2026, 11, 21)).service_date.day, 21
		)

	def test_only_an_unknown_outcome_can_come_from_an_unavailable_service(self):
		with self.assertRaises(ValueError):
			confirmation(unavailable=True)
		self.assertTrue(
			confirmation(outcome=Outcome.UNKNOWN, status="evatr-1001", unavailable=True).unavailable
		)

	def test_a_definite_outcome_keeps_the_answer(self):
		for outcome in (Outcome.VALID, Outcome.INVALID):
			with self.subTest(outcome=outcome), self.assertRaises(ValueError):
				confirmation(outcome=outcome, response_text=None)
		self.assertIsNone(confirmation(outcome=Outcome.UNKNOWN, response_text=None).response_text)

	def test_matches_belong_to_a_qualified_query(self):
		with self.assertRaises(ValueError):
			confirmation(name_match=Match.MATCHES)
		qualified = confirmation(details=Details("Musterhaus GmbH", "musterort"), name_match=Match.MATCHES)
		self.assertTrue(qualified.qualified)
		self.assertFalse(confirmation().qualified)

	def test_only_vies_answers_in_place_of_the_bzst(self):
		with self.assertRaises(ValueError):
			confirmation(fallback_reason="Das BZSt konnte die Anfrage nicht beantworten.")
		fallback = confirmation(
			service=Service.VIES,
			status="VALID",
			fallback_reason="Das BZSt konnte die Anfrage nicht beantworten.",
		)
		self.assertIs(fallback.service, Service.VIES)

	def test_queries_run_from_the_first_to_this_one(self):
		simple = confirmation()
		qualified = confirmation(details=Details("Musterhaus GmbH", "musterort"), previous=simple)
		self.assertEqual(simple.queries(), (simple,))
		self.assertEqual(qualified.queries(), (simple, qualified))

	def test_is_immutable(self):
		record = confirmation()
		with self.assertRaises(AttributeError):
			record.outcome = Outcome.INVALID
		self.assertEqual(replace(record, consultation_id=None).consultation_id, None)


class ValidThroughTest(TestCase):
	"""An answer of the BZSt holds for the moment of its query; for a number it finds not valid then, gueltigAb and
	gueltigBis say when it was valid (evatr-2006) or from when it is (evatr-2002)."""

	FIRST, LAST = date(2026, 6, 1), date(2026, 6, 30)

	def test_a_number_valid_before_and_after_the_days_was_valid_through_them(self):
		self.assertTrue(valid_through(date(2019, 1, 1), date(2026, 7, 15), self.FIRST, self.LAST))
		self.assertTrue(valid_through(date(2026, 6, 1), date(2026, 6, 30), self.FIRST, self.LAST))

	def test_a_number_valid_from_a_day_before_them_is_valid_through_them(self):
		self.assertTrue(valid_through(date(2026, 5, 1), None, self.FIRST, self.LAST))

	def test_a_number_valid_until_a_day_after_them_was_valid_through_them(self):
		self.assertTrue(valid_through(None, date(2026, 7, 1), self.FIRST, self.LAST))

	def test_a_validity_that_begins_or_ends_within_the_days_does_not_cover_them(self):
		self.assertFalse(valid_through(date(2026, 6, 2), None, self.FIRST, self.LAST))
		self.assertFalse(valid_through(date(2019, 1, 1), date(2026, 6, 29), self.FIRST, self.LAST))

	def test_an_answer_without_a_validity_covers_nothing(self):
		self.assertFalse(valid_through(None, None, self.FIRST, self.LAST))
