"""The confirmations of the USt-IdNrn. of business partners: which number a partner holds, whether its confirmation is
current, when the daily renewal asks again and in which order, and what a Sales Invoice behind Kz 41, 42 or 21
needs before it is submitted. The numbers are invented or the examples of the OpenAPI document of the eVatR API."""

from datetime import UTC, date, datetime
from unittest import TestCase

from steuerbote.vatid import partners
from steuerbote.vatid.partners import (
	GOODS,
	MAX_PER_RUN,
	RELEASABLE,
	SERVICES,
	Answer,
	Asked,
	Candidate,
	Finding,
	Kind,
	Level,
	MappingRule,
	Policy,
	Problem,
	Standing,
	Stop,
	TodayQuery,
	age,
	covered_today,
	in_service_hours,
	invoice_finding,
	invoice_kennzahlen,
	is_due,
	kind,
	reason,
	renew,
	renewal_order,
	standing,
)
from steuerbote.vatid.result import Details, Outcome

TODAY = date(2026, 11, 25)
DETAILS = Details("Alpen Handel GmbH", "Wien", "1010", "Ring 1")
VALID = Outcome.VALID
INVALID = Outcome.INVALID


def answer(days_ago: int, outcome: Outcome = VALID, qualified: bool = True, differs: bool = False) -> Answer:
	return Answer(date.fromordinal(TODAY.toordinal() - days_ago), outcome, qualified, differs)


class KindTest(TestCase):
	def test_tells_a_number_the_bzst_confirms_from_one_it_cannot_and_from_a_malformed_one(self):
		cases = {
			None: Kind.MISSING,
			"": Kind.MISSING,
			" - ": Kind.MISSING,
			"ATU12345678": Kind.CONFIRMABLE,
			"atu 123 456 78": Kind.CONFIRMABLE,
			"NL123456789B01": Kind.CONFIRMABLE,
			"DE111111125": Kind.GERMAN,
			"DE 111 111 125": Kind.GERMAN,
			"DE123456789": Kind.MALFORMED,
			"ATU1234567": Kind.MALFORMED,
			"DE12345": Kind.MALFORMED,
			"CHE-123.456.789 MWST": Kind.NOT_CONFIRMABLE,
			"GB123456789": Kind.NOT_CONFIRMABLE,
			"GR123456789": Kind.NOT_CONFIRMABLE,
			"NO123456789MVA": Kind.NOT_CONFIRMABLE,
			"PL-12": Kind.MALFORMED,
			"123456789": Kind.MALFORMED,
			"FR123456789012345": Kind.MALFORMED,
		}
		self.assertEqual({value: kind(value) for value in cases}, cases)

	def test_only_a_confirmable_number_is_sent_and_a_german_one_where_the_company_checks_them(self):
		self.assertEqual([item for item in Kind if item.sent], [Kind.CONFIRMABLE])
		self.assertEqual(
			[item for item in Kind if item.checked(german=True)], [Kind.CONFIRMABLE, Kind.GERMAN]
		)
		self.assertEqual([item for item in Kind if item.checked(german=False)], [Kind.CONFIRMABLE])

	def test_says_what_is_wrong_with_a_number(self):
		self.assertIn("Prüfziffer", reason("DE123456789"))
		self.assertIn("Österreich", reason("ATU1234567"))
		self.assertIn("Länderkennzeichen", reason("CHE123456789"))
		self.assertIsNone(reason("ATU12345678"))
		self.assertIsNone(reason("DE111111125"))
		self.assertIsNone(reason(None))


class AnswerTest(TestCase):
	def test_an_answer_is_valid_or_invalid(self):
		with self.assertRaisesRegex(ValueError, "valid or invalid"):
			Answer(TODAY, Outcome.UNKNOWN)

	def test_its_age_counts_the_days_to_the_reference_and_a_later_answer_as_new(self):
		self.assertEqual(
			[age(answer(days), TODAY) for days in (0, 1, 90, -3)],
			[0, 1, 90, 0],
		)


class StandingTest(TestCase):
	def test_a_partner_no_company_deals_with_is_on_the_worklist_as_not_assigned(self):
		"""Not a standing of the number: the partner deals with no company, so no company asks about it by itself."""
		self.assertEqual(Standing.NOT_ASSIGNED.value, "Not Assigned")
		self.assertTrue(Standing.NOT_ASSIGNED.work)

	def standing(self, value="ATU12345678", last=None, asked=None, max_age=90, details=True):
		return standing(
			kind(value), last, last is not None if asked is None else asked, TODAY, max_age, details
		)

	def test_a_partner_without_a_number_the_bzst_confirms_is_not_on_the_list_unless_the_number_is_wrong(self):
		self.assertEqual(
			[self.standing(value) for value in (None, "DE111111125", "CHE123456789", "PL-12")],
			[None, None, Standing.NOT_CONFIRMABLE, Standing.MALFORMED],
		)

	def test_a_number_is_current_with_a_valid_qualified_answer_within_the_age(self):
		self.assertEqual(self.standing(last=answer(90)), Standing.CURRENT)
		self.assertEqual(self.standing(last=answer(91)), Standing.EXPIRED)
		self.assertEqual(self.standing(last=answer(0), max_age=0), Standing.CURRENT)

	def test_names_what_is_missing(self):
		self.assertEqual(self.standing(), Standing.MISSING)
		self.assertEqual(self.standing(asked=True), Standing.NO_ANSWER)
		self.assertEqual(self.standing(last=answer(5, INVALID)), Standing.INVALID)
		self.assertEqual(self.standing(last=answer(5, qualified=False)), Standing.NOT_QUALIFIED)
		self.assertEqual(
			self.standing(last=answer(5, qualified=False), details=False), Standing.ADDRESS_MISSING
		)
		self.assertEqual(self.standing(last=answer(5, differs=True)), Standing.DETAILS_DIFFER)

	def test_an_old_invalid_answer_stays_invalid(self):
		self.assertEqual(self.standing(last=answer(200, INVALID)), Standing.INVALID)

	def test_a_german_number_stands_once_the_company_checks_german_numbers_and_needs_no_name(self):
		def german(last=None, asked=None):
			return standing(
				kind("DE111111125"),
				last,
				last is not None if asked is None else asked,
				TODAY,
				90,
				False,
				german=True,
			)

		self.assertEqual(german(), Standing.GERMAN_UNCHECKED)
		self.assertEqual(german(asked=True), Standing.NO_ANSWER)
		self.assertEqual(german(answer(5, qualified=False)), Standing.CURRENT)
		self.assertEqual(german(answer(5, INVALID, qualified=False)), Standing.INVALID)
		self.assertEqual(german(answer(91, qualified=False)), Standing.EXPIRED)

	def test_a_valid_answer_of_a_service_outweighs_the_structure_of_the_merkblatt(self):
		self.assertEqual(self.standing("ATU1234567"), Standing.MALFORMED)
		self.assertEqual(self.standing("ATU1234567", last=answer(5)), Standing.CURRENT)

	def test_every_standing_but_current_is_work(self):
		self.assertEqual([item for item in Standing if not item.work], [Standing.CURRENT])


class CoveredTodayTest(TestCase):
	def test_a_definite_answer_of_today_covers_the_same_question(self):
		simple = TodayQuery(VALID, None)
		qualified = TodayQuery(VALID, DETAILS)
		self.assertTrue(covered_today([simple], None))
		self.assertFalse(covered_today([simple], DETAILS))
		self.assertTrue(covered_today([simple, qualified], DETAILS))
		self.assertTrue(covered_today([qualified], None))
		other = Details("Alpen Handel GmbH", "Graz")
		self.assertFalse(covered_today([qualified], other))

	def test_an_invalid_answer_covers_any_question_and_no_answer_covers_none(self):
		self.assertTrue(covered_today([TodayQuery(INVALID, None)], DETAILS))
		self.assertFalse(covered_today([TodayQuery(Outcome.UNKNOWN, None)], None))
		self.assertFalse(covered_today([], None))


class DueTest(TestCase):
	def due(self, last=None, asked_on=None, value="ATU12345678", max_age=90, details=True):
		return is_due(kind(value), last, asked_on, TODAY, max_age, details)

	def test_asks_about_a_confirmable_number_never_confirmed_or_confirmed_too_long_ago(self):
		self.assertTrue(self.due())
		self.assertFalse(self.due(answer(89)))
		self.assertTrue(self.due(answer(90)))
		self.assertTrue(self.due(answer(120, INVALID)))
		self.assertFalse(self.due(answer(10, INVALID)))

	def test_asks_qualified_once_an_address_is_known(self):
		self.assertTrue(self.due(answer(10, qualified=False)))
		self.assertFalse(self.due(answer(10, qualified=False), details=False))

	def test_asks_about_no_number_twice_a_day(self):
		self.assertFalse(self.due(asked_on=TODAY))
		self.assertFalse(self.due(answer(200), asked_on=TODAY))
		self.assertTrue(self.due(asked_on=date(2026, 11, 24)))

	def test_asks_about_no_number_the_bzst_cannot_confirm(self):
		self.assertEqual(
			[self.due(value=value) for value in (None, "DE111111125", "GB123456789", "PL-12", "DE123456789")],
			[False] * 5,
		)

	def test_asks_about_a_german_number_where_the_company_checks_them_and_never_qualified(self):
		def due(last=None, asked_on=None):
			return is_due(kind("DE111111125"), last, asked_on, TODAY, 90, True, german=True)

		self.assertTrue(due())
		self.assertFalse(due(answer(10, qualified=False)))
		self.assertTrue(due(answer(90, qualified=False)))
		self.assertFalse(due(asked_on=TODAY))


class RenewalTest(TestCase):
	def test_asks_about_the_numbers_never_confirmed_first_then_the_oldest(self):
		candidates = [
			Candidate("b", answer(100)),
			Candidate("c", None),
			Candidate("a", answer(120)),
			Candidate("d", answer(100)),
			Candidate("a0", None),
		]
		self.assertEqual([item.key for item in renewal_order(candidates)], ["a0", "c", "a", "b", "d"])

	def renewed(self, answers, limit=MAX_PER_RUN, hours=True):
		asked, pauses = [], []
		queue = list(answers)

		def ask(candidate):
			asked.append(candidate.key)
			return queue.pop(0)

		moment = (
			datetime(2026, 11, 25, 6, 30, tzinfo=UTC) if hours else datetime(2026, 11, 25, 23, tzinfo=UTC)
		)
		candidates = [Candidate(str(index), None) for index in range(len(answers))]
		result = renew(candidates, ask, lambda: pauses.append(1), lambda: moment, limit)
		return result, asked, len(pauses)

	def test_asks_one_after_the_other_with_a_pause_between(self):
		result, asked, pauses = self.renewed([Asked.ANSWERED, Asked.FAILED, Asked.ANSWERED])
		self.assertEqual(asked, ["0", "1", "2"])
		self.assertEqual(pauses, 2)
		self.assertEqual((result.stored, result.failed, result.stop), (("0", "2"), ("1",), None))

	def test_stops_at_the_first_service_that_cannot_answer(self):
		result, asked, _pauses = self.renewed([Asked.ANSWERED, Asked.UNAVAILABLE, Asked.ANSWERED])
		self.assertEqual(asked, ["0", "1"])
		self.assertEqual((result.stored, result.stop), (("0", "1"), Stop.UNAVAILABLE))

	def test_stops_after_the_limit_and_outside_the_hours_of_the_services(self):
		result, asked, _pauses = self.renewed([Asked.ANSWERED] * 3, limit=2)
		self.assertEqual((asked, result.stop), (["0", "1"], Stop.LIMIT))
		result, asked, _pauses = self.renewed([Asked.ANSWERED], hours=False)
		self.assertEqual((asked, result.stop), ([], Stop.OUTSIDE_HOURS))
		result, asked, _pauses = self.renewed([], limit=0)
		self.assertEqual((asked, result.stop), ([], None))

	def test_the_services_answer_from_five_in_the_morning_until_eleven_at_night_in_germany(self):
		def berlin(hour, minute=0, month=11):
			offset = 1 if month in (1, 2, 11, 12) else 2
			return datetime(2026, month, 25, (hour - offset) % 24, minute, tzinfo=UTC)

		self.assertEqual(
			[in_service_hours(berlin(*time)) for time in ((4, 59), (5, 0), (22, 59), (23, 0), (0, 30))],
			[False, True, True, False, False],
		)
		self.assertTrue(in_service_hours(berlin(5, 0, month=7)))
		with self.assertRaisesRegex(ValueError, "time zone"):
			in_service_hours(datetime(2026, 11, 25, 12))


RULES = (
	MappingRule("8125", "41"),
	MappingRule("8130", "42"),
	MappingRule("8336", "21"),
	MappingRule("8400", "81"),
	MappingRule("8743", "41"),
	MappingRule("8338", "45", "21"),
)
STRICT = Policy(Level.BLOCK, 0)
SERVICE = Policy(Level.WARN, 90)


class InvoiceTest(TestCase):
	def test_the_mapping_tells_the_kennzahlen_of_the_income_accounts(self):
		self.assertEqual(invoice_kennzahlen(["8125", "8400", None], RULES), ("41",))
		self.assertEqual(invoice_kennzahlen(["8336", "8130", "8125"], RULES), ("41", "42", "21"))
		self.assertEqual(invoice_kennzahlen(["8338"], RULES), ("21",))
		self.assertEqual(invoice_kennzahlen(["8400", "4711"], RULES), ())

	def finding(
		self, kennzahlen, value="ATU12345678", last=None, asked=False, goods=STRICT, services=SERVICE
	):
		return invoice_finding(kennzahlen, kind(value), last, asked, TODAY, goods, services)

	def test_a_supply_of_goods_needs_a_valid_confirmation_of_the_day(self):
		self.assertIsNone(self.finding(("41",), last=answer(0, qualified=False)))
		self.assertEqual(
			self.finding(("41",), last=answer(1)),
			Finding(Problem.STALE, Level.BLOCK, ("41",), 1, 0),
		)
		self.assertEqual(self.finding(("42",)), Finding(Problem.UNCONFIRMED, Level.BLOCK, ("42",)))
		self.assertEqual(self.finding(("41",), asked=True), Finding(Problem.NO_ANSWER, Level.BLOCK, ("41",)))
		self.assertEqual(
			self.finding(("41",), last=answer(0, INVALID)),
			Finding(Problem.INVALID, Level.BLOCK, ("41",), 0, 0),
		)

	def test_a_number_the_bzst_cannot_confirm_never_passes(self):
		self.assertEqual(
			[self.finding(("41",), value).problem for value in (None, "DE111111125", "GB123456789", "PL-12")],
			[Problem.NO_VAT_ID, Problem.GERMAN, Problem.NOT_CONFIRMABLE, Problem.MALFORMED],
		)

	def test_a_service_needs_a_qualified_confirmation_within_the_age(self):
		self.assertIsNone(self.finding(("21",), last=answer(90)))
		self.assertEqual(
			self.finding(("21",), last=answer(91)), Finding(Problem.STALE, Level.WARN, ("21",), 91, 90)
		)
		self.assertEqual(
			self.finding(("21",), last=answer(3, qualified=False)),
			Finding(Problem.NOT_QUALIFIED, Level.WARN, ("21",), 3, 90),
		)

	def test_goods_and_services_together_follow_the_goods_then_ask_for_the_qualified_confirmation(self):
		self.assertEqual(
			self.finding(("41", "21"), last=answer(2)), Finding(Problem.STALE, Level.BLOCK, ("41",), 2, 0)
		)
		self.assertEqual(
			self.finding(("41", "21"), last=answer(0, qualified=False)),
			Finding(Problem.NOT_QUALIFIED, Level.WARN, ("21",), 0, 90),
		)
		self.assertIsNone(self.finding(("41", "21"), last=answer(0)))

	def test_a_policy_switched_off_finds_nothing_and_an_invoice_without_these_kennzahlen_needs_nothing(self):
		off = Policy(Level.OFF, 0)
		self.assertIsNone(self.finding(("41",), goods=off))
		self.assertIsNone(self.finding(("21",), services=off))
		self.assertIsNone(self.finding((), value=None))

	def test_a_valid_answer_outweighs_the_structure_of_the_merkblatt_at_the_invoice(self):
		self.assertEqual(self.finding(("41",), "ATU1234567").problem, Problem.MALFORMED)
		self.assertIsNone(self.finding(("41",), "ATU1234567", last=answer(0)))

	def test_a_policy_needs_an_age_from_zero_on(self):
		with self.assertRaisesRegex(ValueError, "from 0 on"):
			Policy(Level.BLOCK, -1)

	def test_the_kennzahlen_of_goods_and_services_are_those_of_the_zm(self):
		self.assertEqual((GOODS, SERVICES), (("41", "42"), ("21",)))


class ReleaseTest(TestCase):
	def test_a_reason_releases_a_number_that_lacks_a_confirmation_but_not_one_that_is_missing_or_wrong(self):
		"""As a line of the Zusammenfassende Meldung: a release lifts an unconfirmed or invalid number, never a missing or
		malformed one, which the invoice has to correct."""
		self.assertEqual(
			RELEASABLE,
			frozenset(
				{
					Problem.UNCONFIRMED,
					Problem.NO_ANSWER,
					Problem.INVALID,
					Problem.STALE,
					Problem.NOT_QUALIFIED,
				}
			),
		)
		self.assertTrue(Finding(Problem.INVALID, Level.BLOCK, ("41",)).releasable)
		self.assertFalse(Finding(Problem.NO_VAT_ID, Level.BLOCK, ("41",)).releasable)


class PartyLabelTest(TestCase):
	"""ERPNext names a customer or supplier by its name or by a number of a naming series; whoever reads a list or a
	hint needs both, the name to know the partner and the ID to find it."""

	def test_a_partner_named_by_number_reads_as_its_name_and_its_number(self):
		self.assertEqual(partners.party_label("10042", "Muster GmbH"), "Muster GmbH (10042)")
		self.assertEqual(
			partners.party_label("70042", " Beispiel Lieferant KG "), "Beispiel Lieferant KG (70042)"
		)

	def test_a_partner_named_by_its_name_reads_once(self):
		self.assertEqual(partners.party_label("Muster GmbH", "Muster GmbH"), "Muster GmbH")
		self.assertEqual(partners.party_label("Muster GmbH", None), "Muster GmbH")

	def test_a_name_without_an_id_and_nothing_at_all(self):
		self.assertEqual(partners.party_label(None, "Muster GmbH"), "Muster GmbH")
		self.assertEqual(partners.party_label(None, None), "")
