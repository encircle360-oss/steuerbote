"""When a mapping takes over the defaults of today: Steuerbote einrichten loads them into a mapping that waits for them,
as into a new one, and leaves every other mapping as it is; Vorgaben aktualisieren notes them once it takes over a
difference or the user declined them all."""

from unittest import TestCase

from steuerbote.mappings.taking_over import notes_defaults, waits_for_defaults

TODAY = "SKR04 Taxonomie 6.9 2026.1"
REVISION_0 = "SKR04 Taxonomie 6.9 2026.0"
RULE = {"account_number": "1800", "concept": "bs.ass.currAss.cashEquiv.bank"}
EXCLUDED = {"account_number": "9000", "reason": "Saldenvorträge der Klasse 9"}


class WaitsForDefaultsTest(TestCase):
	def test_a_mapping_without_rows_waits_for_defaults_other_than_those_it_took_over(self):
		"""As a mapping made while the defaults were the empty table of revision 0, or one of another chart."""
		for taken_over in (REVISION_0, "SKR03 Taxonomie 6.9 2026.1"):
			with self.subTest(taken_over=taken_over):
				self.assertTrue(waits_for_defaults(([], [], []), taken_over, TODAY))

	def test_a_mapping_without_rows_that_never_took_over_defaults_waits_for_them(self):
		for taken_over in (None, ""):
			with self.subTest(taken_over=taken_over):
				self.assertTrue(waits_for_defaults(([], []), taken_over, TODAY))

	def test_a_row_in_any_table_ends_the_wait(self):
		for tables in (([RULE], [], []), ([], [], [EXCLUDED])):
			with self.subTest(tables=tables):
				self.assertFalse(waits_for_defaults(tables, REVISION_0, TODAY))

	def test_a_mapping_without_rows_that_took_over_the_defaults_of_today_stays_as_it_is(self):
		"""Its base holds the defaults of today, so every row of them it lacks is one the user removed or one of an
		account the company does not have."""
		self.assertFalse(waits_for_defaults(([], [], []), TODAY, TODAY))

	def test_a_chart_without_defaults_waits_for_none(self):
		self.assertFalse(waits_for_defaults(([], []), None, None))


class NotesDefaultsTest(TestCase):
	def test_taking_over_a_difference_notes_the_defaults_of_today(self):
		for acknowledged in (False, True):
			with self.subTest(acknowledged=acknowledged):
				self.assertTrue(notes_defaults(1, acknowledged))
		self.assertTrue(notes_defaults(6, False))

	def test_taking_over_none_notes_them_only_when_the_user_declined_them(self):
		"""Noted, the defaults of today are the base, and every difference left counts as the user's own: without the
		word of the user, the differences stay proposed."""
		self.assertTrue(notes_defaults(0, True))
		self.assertFalse(notes_defaults(0, False))

	def test_the_answer_is_a_bool_whatever_the_flag_of_the_request(self):
		"""A request gives the flag as 1 or 0, which the type check of Frappe leaves a number."""
		self.assertIs(notes_defaults(0, 1), True)
		self.assertIs(notes_defaults(0, 0), False)
