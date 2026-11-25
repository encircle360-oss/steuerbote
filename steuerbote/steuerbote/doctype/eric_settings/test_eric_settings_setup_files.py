"""The step of Steuerbote einrichten for the ERiC Settings, as hooks.py names it, without a bench."""

import ast
import csv
from pathlib import Path
from unittest import TestCase

from steuerbote import hooks
from steuerbote.setup.steps import Step

FOLDER = Path(__file__).resolve().parent
TRANSLATIONS = Path(hooks.__file__).resolve().parent / "translations" / "de.csv"


class SetupStepTest(TestCase):
	def test_the_hook_runs_the_step_of_the_eric_settings_after_the_mappings(self):
		(entry,) = (entry for entry in hooks.steuerbote_setup_steps if entry["key"] == "eric_settings")
		step = Step.from_hook(entry)
		self.assertEqual(
			(step.key, step.label, step.order, step.run, step.needs),
			(
				"eric_settings",
				"ERiC Settings",
				60,
				"steuerbote.steuerbote.doctype.eric_settings.setup.run",
				(),
			),
		)
		self.assertRegex(
			(FOLDER / "setup.py").read_text(encoding="utf-8"), r"\ndef run\(context: SetupContext\)"
		)

	def test_every_note_of_the_step_reads_in_german(self):
		tree = ast.parse((FOLDER / "setup.py").read_text(encoding="utf-8"))
		constants = {
			node.targets[0].id: node.value.value
			for node in tree.body
			if isinstance(node, ast.Assign)
			and isinstance(node.targets[0], ast.Name)
			and isinstance(node.value, ast.Constant)
			and isinstance(node.value.value, str)
		}
		(listed,) = (
			node.value
			for node in tree.body
			if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "MESSAGES"
		)
		messages = {constants[name.id] for name in listed.elts}
		with TRANSLATIONS.open(encoding="utf-8", newline="") as file:
			translated = {row[0] for row in csv.reader(file) if row}
		self.assertEqual(len(messages), 2)
		self.assertEqual(sorted(messages - translated), [])
