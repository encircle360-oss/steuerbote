from decimal import Decimal
from unittest import TestCase

from steuerbote.jahresmeldung.overrides import (
	Columns,
	Correction,
	ManualLine,
	OverrideError,
	Problem,
	changed,
	correction_of,
	kept,
	manual_lines,
	recalculated,
	reported,
	restored,
)

# The columns of a line table such as that of the Umsatzsteuererklärung: the Feldkennung, the amount the form takes
# and the exact amount of the ledger, and the label of the line.
COLUMNS = Columns(key="element", amounts=("form", "ledger"), described=("label",))
REASON = "Gutschrift vom 30. Dezember 2026, gebucht im Januar"


def row(element, form="0", ledger="0", label="", correction="0", reason="", manual=0, name=None, **more):
	return {
		"name": name,
		"element": element,
		"form": Decimal(form),
		"ledger": Decimal(ledger),
		"label": label,
		"correction": Decimal(correction),
		"correction_reason": reason,
		"manual": manual,
		**more,
	}


class ColumnsTest(TestCase):
	def test_the_standard_columns_of_a_line_table(self):
		columns = Columns()
		self.assertEqual(
			(columns.key, columns.amounts, columns.described, columns.correction, columns.reason),
			("key", ("computed",), (), "correction", "correction_reason"),
		)
		self.assertEqual((columns.reported, columns.manual), ("reported", "manual"))

	def test_berechnen_fills_the_key_its_amounts_and_the_description(self):
		self.assertEqual(COLUMNS.filled, ("element", "form", "ledger", "label"))
		self.assertEqual(COLUMNS.amount, "form")

	def test_needs_an_amount_column(self):
		with self.assertRaises(ValueError):
			Columns(amounts=())


class CorrectionTest(TestCase):
	def test_a_correction_files_another_amount_once_it_has_a_reason(self):
		self.assertEqual(
			correction_of(row("E3003303", "1000", correction="900.5", reason=f"  {REASON} "), COLUMNS),
			Correction(Decimal("900.50"), REASON),
		)

	def test_a_correction_to_zero_is_filed_too(self):
		self.assertEqual(
			correction_of(row("E3003303", "1000", reason=REASON), COLUMNS),
			Correction(Decimal("0.00"), REASON),
		)

	def test_a_row_without_correction_and_reason_has_none(self):
		self.assertIsNone(correction_of(row("E3003303", "1000", reason="  "), COLUMNS))
		self.assertIsNone(correction_of({"element": "E3003303"}, COLUMNS))

	def test_a_correction_without_a_reason_is_refused_rather_than_ignored(self):
		with self.assertRaises(OverrideError) as raised:
			correction_of(row("E3003303", "1000", correction="900"), COLUMNS)
		self.assertEqual(
			(raised.exception.problem, raised.exception.key), (Problem.MISSING_REASON, "E3003303")
		)

	def test_takes_the_amounts_frappe_hands_out(self):
		"""Frappe gives a currency field as a float, a string or nothing; the amount is kept in cents."""
		for value, amount in (
			(900.5, "900.50"),
			("900.5", "900.50"),
			(None, "0.00"),
			(Decimal("1.005"), "1.01"),
		):
			with self.subTest(value=value):
				self.assertEqual(
					correction_of(
						{"element": "E1", "correction": value, "correction_reason": REASON}, COLUMNS
					).amount,
					Decimal(amount),
				)

	def test_a_correction_holds_a_decimal_and_a_reason(self):
		with self.assertRaises(TypeError):
			Correction(900.5, REASON)
		with self.assertRaises(OverrideError):
			Correction(Decimal("900.50"), " ")


class ReportedTest(TestCase):
	def test_a_line_reports_what_berechnen_computed_for_the_form(self):
		self.assertEqual(reported(row("E3003303", "1000", "999.99"), COLUMNS), Decimal("1000.00"))

	def test_a_correction_with_its_reason_replaces_it(self):
		self.assertEqual(
			reported(row("E3003303", "1000", correction="900", reason=REASON), COLUMNS), Decimal("900.00")
		)

	def test_a_line_by_hand_reports_its_amount(self):
		self.assertEqual(
			reported(row("E3005901", manual=1, correction="250", reason=REASON), COLUMNS), Decimal("250.00")
		)

	def test_a_line_by_hand_needs_its_reason(self):
		with self.assertRaises(OverrideError) as raised:
			reported(row("E3005901", manual=1, correction="250"), COLUMNS)
		self.assertIs(raised.exception.problem, Problem.MISSING_REASON)
		with self.assertRaises(OverrideError):
			reported(row("E3005901", manual=1), COLUMNS)

	def test_names_the_lines_by_hand_for_a_module_that_computes_with_them(self):
		rows = [
			row("E3003303", "1000"),
			row("E3003303", manual=1, correction="10.5", reason=REASON),
			row("E3005901", manual=1, correction="-4", reason="Storno"),
		]
		self.assertEqual(
			manual_lines(rows, COLUMNS),
			(
				ManualLine("E3003303", Decimal("10.50"), REASON),
				ManualLine("E3005901", Decimal("-4.00"), "Storno"),
			),
		)

	def test_a_line_by_hand_holds_a_key_and_a_reason(self):
		with self.assertRaises(OverrideError) as raised:
			manual_lines([row(" ", manual=1, correction="1", reason=REASON)], COLUMNS)
		self.assertIs(raised.exception.problem, Problem.NO_KEY)


class RecalculatedTest(TestCase):
	"""Berechnen writes the lines it computed and keeps the corrections and the lines by hand."""

	def test_writes_the_lines_berechnen_computed_with_their_reported_amount(self):
		self.assertEqual(
			recalculated([row("E3003303", "1000", "999.99", "Umsätze zu 19 %")], [], COLUMNS),
			[
				{
					"element": "E3003303",
					"form": Decimal("1000"),
					"ledger": Decimal("999.99"),
					"label": "Umsätze zu 19 %",
					"correction": Decimal("0"),
					"correction_reason": "",
					"reported": Decimal("1000.00"),
					"manual": 0,
				}
			],
		)

	def test_keeps_the_correction_of_a_line_for_its_key(self):
		before = [row("E3003303", "800", correction="900", reason=REASON, name="r1")]
		(line,) = recalculated([row("E3003303", "1000", "999.99")], before, COLUMNS)
		self.assertEqual(
			(line["form"], line["correction"], line["correction_reason"], line["reported"]),
			(Decimal("1000"), Decimal("900.00"), REASON, Decimal("900.00")),
		)
		self.assertNotIn("name", line)

	def test_keeps_a_correction_of_a_line_berechnen_no_longer_computes_with_an_empty_computation(self):
		before = [
			row("E3004401", "500", "499.5", "Umsätze zu 7 %", correction="450", reason=REASON, name="r2")
		]
		(line,) = recalculated([], before, COLUMNS)
		self.assertEqual(
			(line["element"], line["form"], line["ledger"], line["label"], line["reported"], line["manual"]),
			("E3004401", Decimal("0"), Decimal("0"), "Umsätze zu 7 %", Decimal("450.00"), 0),
		)
		self.assertNotIn("name", line)

	def test_drops_a_line_without_a_correction_that_berechnen_no_longer_computes(self):
		self.assertEqual(recalculated([], [row("E3004401", "500", name="r2")], COLUMNS), [])

	def test_keeps_the_lines_by_hand_after_the_lines_it_computed(self):
		by_hand = row("E3005901", manual=1, correction="250", reason=REASON, name="r3", paragraph="§ 4 Nr. 8")
		lines = recalculated([row("E3003303", "1000")], [by_hand], COLUMNS)
		self.assertEqual([line["element"] for line in lines], ["E3003303", "E3005901"])
		self.assertEqual(
			{key: lines[1][key] for key in ("manual", "form", "correction", "reported", "paragraph")},
			{
				"manual": 1,
				"form": Decimal("0"),
				"correction": Decimal("250.00"),
				"reported": Decimal("250.00"),
				"paragraph": "§ 4 Nr. 8",
			},
		)

	def test_refuses_a_key_berechnen_computed_twice(self):
		with self.assertRaises(OverrideError) as raised:
			recalculated([row("E3003303", "1"), row("E3003303", "2")], [], COLUMNS)
		self.assertEqual((raised.exception.problem, raised.exception.key), (Problem.DUPLICATE, "E3003303"))

	def test_refuses_a_correction_without_a_reason_before_it_is_lost(self):
		with self.assertRaises(OverrideError):
			recalculated([row("E3003303", "1000")], [row("E3003303", "800", correction="900")], COLUMNS)


class RestoredTest(TestCase):
	"""Frappe keeps no read-only field from a save through its API: a save takes what the company enters on a line, and
	what Berechnen computed stays."""

	def test_keeps_what_berechnen_computed_and_takes_the_correction(self):
		stored = [row("E3003303", "1000", "999.99", "Umsätze zu 19 %", name="r1")]
		sent = [row("E3009999", "5", "5", "anders", correction="900", reason=REASON, name="r1", manual=1)]
		(line,) = restored(stored, sent, COLUMNS)
		self.assertEqual(
			{key: line[key] for key in ("name", "element", "form", "ledger", "label", "manual", "reported")},
			{
				"name": "r1",
				"element": "E3003303",
				"form": Decimal("1000"),
				"ledger": Decimal("999.99"),
				"label": "Umsätze zu 19 %",
				"manual": 0,
				"reported": Decimal("900.00"),
			},
		)
		self.assertEqual((line["correction"], line["correction_reason"]), (Decimal("900"), REASON))

	def test_a_new_line_is_a_line_by_hand_with_nothing_computed(self):
		sent = [row("E3005901", "5", "5", correction="250", reason=REASON, name="new-row-1")]
		(line,) = restored([], sent, COLUMNS)
		self.assertEqual(
			{key: line[key] for key in ("element", "form", "ledger", "manual", "reported")},
			{
				"element": "E3005901",
				"form": Decimal("0"),
				"ledger": Decimal("0"),
				"manual": 1,
				"reported": Decimal("250.00"),
			},
		)

	def test_a_line_by_hand_takes_the_key_it_is_sent_with(self):
		stored = [row("E3005901", manual=1, correction="250", reason=REASON, name="r3")]
		(line,) = restored(
			stored, [row("E3005902", manual=0, correction="260", reason=REASON, name="r3")], COLUMNS
		)
		self.assertEqual(
			(line["element"], line["manual"], line["reported"]), ("E3005902", 1, Decimal("260.00"))
		)

	def test_a_line_berechnen_computed_stays(self):
		"""Its amount would drop out of the filing unnoticed; a correction with a reason files another amount."""
		stored = [
			row("E3003303", "1000", name="r1"),
			row("E3005901", manual=1, correction="1", reason=REASON, name="r3"),
		]
		with self.assertRaises(OverrideError) as raised:
			restored(stored, [stored[1]], COLUMNS)
		self.assertEqual((raised.exception.problem, raised.exception.key), (Problem.REMOVED, "E3003303"))
		self.assertEqual(len(restored(stored, [stored[0]], COLUMNS)), 1)

	def test_refuses_a_correction_without_a_reason(self):
		with self.assertRaises(OverrideError):
			restored(
				[row("E3003303", "1000", name="r1")], [row("E3003303", correction="900", name="r1")], COLUMNS
			)

	def test_refuses_a_key_twice_among_the_lines_berechnen_computed(self):
		stored = [row("E3003303", "1", name="r1"), row("E3003303", "2", name="r2")]
		with self.assertRaises(OverrideError) as raised:
			restored(stored, stored, COLUMNS)
		self.assertIs(raised.exception.problem, Problem.DUPLICATE)


class KeptTest(TestCase):
	"""Before a document is transmitted, made into a file or submitted, the amounts its lines report are computed again
	from what they hold."""

	def test_the_stored_amounts_are_those_the_lines_give(self):
		lines = recalculated(
			[row("E3003303", "1000")], [row("E3003303", correction="900", reason=REASON)], COLUMNS
		)
		stored = [{**line, "name": "r1"} for line in lines]
		self.assertTrue(kept(stored, stored, COLUMNS))

	def test_an_amount_changed_past_the_save_is_found(self):
		stored = [{**line, "name": "r1"} for line in recalculated([row("E3003303", "1000")], [], COLUMNS)]
		changed_past = [{**stored[0], "correction": Decimal("900"), "correction_reason": REASON}]
		self.assertFalse(kept(changed_past, stored, COLUMNS))
		self.assertFalse(kept(stored, [{**stored[0], "reported": Decimal("1")}], COLUMNS))

	def test_a_line_more_or_less_is_found(self):
		stored = [{**line, "name": "r1"} for line in recalculated([row("E3003303", "1000")], [], COLUMNS)]
		self.assertFalse(kept([], stored, COLUMNS))
		self.assertFalse(kept(stored, [], COLUMNS))

	def test_an_entry_the_lines_refuse_is_no_amount_kept(self):
		stored = [{**line, "name": "r1"} for line in recalculated([row("E3003303", "1000")], [], COLUMNS)]
		self.assertFalse(kept([{**stored[0], "correction": Decimal("900")}], stored, COLUMNS))


class ChangedTest(TestCase):
	"""A save that changes what a line reports leaves the document calculated, until Berechnen checks it again."""

	def setUp(self):
		self.stored = [
			{**line, "name": f"r{index}"}
			for index, line in enumerate(
				recalculated(
					[row("E3003303", "1000")],
					[row("E3005901", manual=1, correction="1", reason=REASON)],
					COLUMNS,
				)
			)
		]

	def test_the_same_amounts_change_nothing(self):
		self.assertFalse(
			changed(
				self.stored,
				[{**line, "correction_reason": line["correction_reason"]} for line in self.stored],
				COLUMNS,
			)
		)

	def test_another_reason_for_the_same_amount_changes_nothing(self):
		self.assertFalse(
			changed(
				self.stored,
				[self.stored[0], {**self.stored[1], "correction_reason": "Andere Begründung"}],
				COLUMNS,
			)
		)

	def test_a_correction_changes_what_berechnen_checked(self):
		corrected = [
			{**self.stored[0], "correction": Decimal("900"), "correction_reason": REASON},
			self.stored[1],
		]
		self.assertTrue(changed(self.stored, corrected, COLUMNS))

	def test_a_line_by_hand_more_or_less_changes_it(self):
		self.assertTrue(changed(self.stored, self.stored[:1], COLUMNS))
		self.assertTrue(
			changed(
				self.stored, [*self.stored, row("E3005902", manual=1, correction="2", reason=REASON)], COLUMNS
			)
		)
