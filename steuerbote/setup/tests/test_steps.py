from unittest import TestCase

from steuerbote.setup.steps import (
	CYCLE,
	DUPLICATE_STEP,
	MESSAGES,
	MISSING_FIELDS,
	NEEDS_ITSELF,
	NO_LABEL,
	NOT_A_FUNCTION,
	NOT_A_KEY,
	NOT_A_STEP,
	NOT_AN_ACTION,
	NOT_AN_ORDER,
	UNKNOWN_FIELDS,
	UNKNOWN_NEED,
	Action,
	Note,
	Outcome,
	SetupError,
	Step,
	StepResult,
	changed,
	missing_needs,
	plan,
)

RUN = "steuerbote.steuerbote.setup.make_vat_return_settings"


def step(key: str, order: int = 10, needs: tuple[str, ...] = ()) -> Step:
	return Step(key, key.replace("_", " ").title(), order, RUN, needs)


def keys(steps: tuple[Step, ...]) -> list[str]:
	return [step.key for step in steps]


class StepTest(TestCase):
	def test_a_step_is_plain_data(self):
		made = Step("annual_filing_settings", "Annual Filing Settings", 40, RUN, ("vat_return_settings",))
		self.assertEqual(
			(made.key, made.label, made.order, made.run, made.needs),
			("annual_filing_settings", "Annual Filing Settings", 40, RUN, ("vat_return_settings",)),
		)
		self.assertEqual(Step("a", "A", 1, RUN).needs, ())

	def test_a_key_is_lowercase_with_digits_and_underscores(self):
		for key in ("", "Settings", "1st", "vat-return", "vat return", None, 7):
			with self.subTest(key=key), self.assertRaises(SetupError) as raised:
				Step(key, "Label", 10, RUN)  # type: ignore[arg-type]
			self.assertEqual(raised.exception.template, NOT_A_KEY)
		self.assertEqual(Step("step_2", "Label", 10, RUN).key, "step_2")

	def test_a_step_has_a_label(self):
		for label in ("", "  ", None):
			with self.subTest(label=label), self.assertRaises(SetupError) as raised:
				Step("a", label, 10, RUN)  # type: ignore[arg-type]
			self.assertEqual((raised.exception.template, raised.exception.values), (NO_LABEL, ("a",)))

	def test_the_order_is_a_whole_number(self):
		for order in (1.5, "10", True, None):
			with self.subTest(order=order), self.assertRaises(SetupError) as raised:
				Step("a", "A", order, RUN)  # type: ignore[arg-type]
			self.assertEqual(
				(raised.exception.template, raised.exception.values), (NOT_AN_ORDER, ("a", order))
			)
		self.assertEqual(Step("a", "A", -5, RUN).order, -5)

	def test_run_is_the_dotted_path_of_a_function(self):
		for run in ("", "make_settings", "steuerbote.", ".steuerbote.setup", "steuerbote setup.run", None):
			with self.subTest(run=run), self.assertRaises(SetupError) as raised:
				Step("a", "A", 10, run)  # type: ignore[arg-type]
			self.assertEqual(raised.exception.template, NOT_A_FUNCTION)

	def test_needs_are_keys_of_steps(self):
		with self.assertRaises(SetupError) as raised:
			Step("a", "A", 10, RUN, ("Not A Key",))
		self.assertEqual((raised.exception.template, raised.exception.values), (NOT_A_KEY, ("Not A Key",)))
		with self.assertRaises(SetupError) as raised:
			Step("a", "A", 10, RUN, "b")  # type: ignore[arg-type]
		self.assertEqual(raised.exception.template, NOT_A_KEY)

	def test_a_need_named_twice_counts_once(self):
		self.assertEqual(Step("a", "A", 10, RUN, ("b", "c", "b")).needs, ("b", "c"))

	def test_a_step_cannot_need_itself(self):
		with self.assertRaises(SetupError) as raised:
			Step("a", "A", 10, RUN, ("a",))
		self.assertEqual((raised.exception.template, raised.exception.values), (NEEDS_ITSELF, ("a",)))

	def test_the_message_names_the_step(self):
		error = SetupError(UNKNOWN_NEED, "income_tax_mapping", "balance_sheet_mapping")
		self.assertEqual(
			str(error),
			"The setup step income_tax_mapping needs balance_sheet_mapping, which is no setup step.",
		)
		self.assertEqual(error.values, ("income_tax_mapping", "balance_sheet_mapping"))


class FromHookTest(TestCase):
	def test_an_entry_of_the_hook_is_a_dict_with_the_fields_of_a_step(self):
		entry = {
			"key": "balance_sheet_mapping",
			"label": "Balance Sheet Mapping",
			"order": 50,
			"needs": ["vat_return_settings"],
			"run": "steuerbote.steuerbote.doctype.balance_sheet_mapping.setup.run",
		}
		self.assertEqual(
			Step.from_hook(entry),
			Step(
				"balance_sheet_mapping",
				"Balance Sheet Mapping",
				50,
				"steuerbote.steuerbote.doctype.balance_sheet_mapping.setup.run",
				("vat_return_settings",),
			),
		)

	def test_needs_may_be_left_out_or_empty(self):
		for entry in (
			{"key": "a", "label": "A", "order": 1, "run": RUN},
			{"key": "a", "label": "A", "order": 1, "run": RUN, "needs": None},
		):
			with self.subTest(entry=entry):
				self.assertEqual(Step.from_hook(entry).needs, ())

	def test_an_entry_that_is_no_dict_is_refused(self):
		for entry in ("steuerbote.setup.run", ["a"], None):
			with self.subTest(entry=entry), self.assertRaises(SetupError) as raised:
				Step.from_hook(entry)
			self.assertEqual(raised.exception.template, NOT_A_STEP)

	def test_an_entry_names_every_field_a_step_needs(self):
		with self.assertRaises(SetupError) as raised:
			Step.from_hook({"key": "a", "order": 1})
		self.assertEqual(
			(raised.exception.template, raised.exception.values), (MISSING_FIELDS, ("a", "label, run"))
		)

	def test_an_entry_has_no_field_a_step_does_not_know(self):
		with self.assertRaises(SetupError) as raised:
			Step.from_hook({"key": "a", "label": "A", "order": 1, "run": RUN, "roles": [], "after": "b"})
		self.assertEqual(
			(raised.exception.template, raised.exception.values), (UNKNOWN_FIELDS, ("a", "after, roles"))
		)

	def test_needs_is_a_list_not_a_text(self):
		with self.assertRaises(SetupError) as raised:
			Step.from_hook({"key": "a", "label": "A", "order": 1, "run": RUN, "needs": "b"})
		self.assertEqual((raised.exception.template, raised.exception.values), (NOT_A_KEY, ("b",)))


class PlanTest(TestCase):
	def test_steps_run_by_order_and_then_key(self):
		self.assertEqual(keys(plan([step("c", 20), step("b", 10), step("a", 20)])), ["b", "a", "c"])

	def test_a_step_runs_after_every_step_it_needs_whatever_its_order(self):
		steps = [step("filing_period", 5, ("settings", "mapping")), step("mapping", 20), step("settings", 10)]
		self.assertEqual(keys(plan(steps)), ["settings", "mapping", "filing_period"])

	def test_a_step_runs_as_soon_as_its_needs_have_run(self):
		steps = [step("a", 10), step("b", 30), step("c", 20, ("a",)), step("d", 25, ("b",))]
		self.assertEqual(keys(plan(steps)), ["a", "c", "b", "d"])

	def test_the_order_does_not_depend_on_the_order_given(self):
		steps = [step("a", 10), step("b", 10), step("c", 5, ("b",)), step("d", 30)]
		self.assertEqual(keys(plan(steps)), keys(plan(reversed(steps))))

	def test_no_steps_make_an_empty_plan(self):
		self.assertEqual(plan([]), ())

	def test_a_key_is_defined_once(self):
		with self.assertRaises(SetupError) as raised:
			plan([step("a"), step("b"), step("a", 30)])
		self.assertEqual((raised.exception.template, raised.exception.values), (DUPLICATE_STEP, ("a",)))

	def test_a_need_names_a_step_of_the_plan(self):
		with self.assertRaises(SetupError) as raised:
			plan([step("a"), step("b", 20, ("c",))])
		self.assertEqual((raised.exception.template, raised.exception.values), (UNKNOWN_NEED, ("b", "c")))

	def test_steps_that_need_each_other_are_refused(self):
		with self.assertRaises(SetupError) as raised:
			plan([step("a", 10, ("c",)), step("b", 20, ("a",)), step("c", 30, ("b",)), step("d", 40)])
		self.assertEqual((raised.exception.template, raised.exception.values), (CYCLE, ("a, b, c",)))


class ResultTest(TestCase):
	def test_a_result_keeps_its_outcome_notes_and_document(self):
		result = StepResult(
			"created", [Note("{0} made.", ["X"], open=True)], ("VAT Return Settings", "X GmbH")
		)  # type: ignore[arg-type]
		self.assertEqual(result.outcome, Outcome.CREATED)
		self.assertEqual(result.notes, (Note("{0} made.", ("X",), True),))
		self.assertEqual(result.document, ("VAT Return Settings", "X GmbH"))
		self.assertEqual(StepResult(Outcome.SKIPPED).notes, ())
		self.assertIsNone(StepResult(Outcome.SKIPPED).action)

	def test_a_result_may_offer_an_action_the_user_starts_from_the_page(self):
		action = Action("Relabel the Field", "steuerbote.steuerbote.vat_id_setup.relabel_tax_id")
		result = StepResult(Outcome.UNDECIDED, (Note("Open.", open=True),), action=action)
		self.assertEqual(result.action, action)

	def test_an_action_has_a_label_and_calls_a_function(self):
		for label, method in (("", "a.b"), (" ", "a.b"), ("Relabel", "relabel"), ("Relabel", None)):
			with self.subTest(label=label, method=method), self.assertRaises(SetupError) as raised:
				Action(label, method)  # type: ignore[arg-type]
			self.assertEqual(raised.exception.template, NOT_AN_ACTION)
		self.assertIn(NOT_AN_ACTION, MESSAGES)

	def test_a_step_misses_the_needs_whose_documents_are_missing(self):
		filing_period = step("filing_period", 30, ("settings", "mapping"))
		self.assertEqual(missing_needs(filing_period, {}), ("settings", "mapping"))
		for outcome, missing in (
			(Outcome.CREATED, ()),
			(Outcome.SKIPPED, ()),
			(Outcome.UNDECIDED, ("mapping",)),
			(Outcome.FAILED, ("mapping",)),
			(Outcome.BLOCKED, ("mapping",)),
		):
			with self.subTest(outcome=outcome):
				results = {"settings": StepResult(Outcome.SKIPPED), "mapping": StepResult(outcome)}
				self.assertEqual(missing_needs(filing_period, results), missing)

	def test_a_run_changed_something_only_if_a_step_created_something(self):
		self.assertFalse(changed([]))
		self.assertFalse(
			changed(StepResult(outcome) for outcome in Outcome if outcome is not Outcome.CREATED)
		)
		self.assertTrue(changed([StepResult(Outcome.SKIPPED), StepResult(Outcome.CREATED)]))

	def test_every_message_is_an_english_template(self):
		self.assertEqual(len(set(MESSAGES)), 12)
		for message in MESSAGES:
			with self.subTest(message=message):
				self.assertTrue(message.endswith("."))
				self.assertIn("{0}", message)
