"""The summary of the messages of an ELSTER Transmission, without a bench."""

import json
from pathlib import Path
from unittest import TestCase

from steuerbote.eric.result import ERROR, HINT
from steuerbote.steuerbote.doctype.elster_transmission import messages

MESSAGE_DOCTYPE = (
	Path(__file__).resolve().parents[1] / "elster_transmission_message" / "elster_transmission_message.json"
)


class SummaryTest(TestCase):
	def test_counts_the_errors_and_hints_and_keeps_the_first_three_of_each(self):
		rows = [
			{"severity": "hint", "code": "610001003", "text": "Hinweise während der Plausibilitätsprüfung."},
			{"severity": "error", "code": "11085153", "text": "Das Jahr des Wechsels ..."},
			*(
				{"severity": "hint", "code": f"1108515{index}", "text": f"Hinweis {index}"}
				for index in range(4)
			),
		]
		summary = messages.summary(rows)
		self.assertEqual((summary["errors"], summary["hints"]), (1, 5))
		self.assertEqual(summary["first_errors"], [{"code": "11085153", "text": "Das Jahr des Wechsels ..."}])
		self.assertEqual(
			[message["code"] for message in summary["first_hints"]], ["610001003", "11085150", "11085151"]
		)

	def test_a_message_of_steuerbote_may_come_without_a_code(self):
		summary = messages.summary([{"severity": "error", "code": None, "text": "Der Lauf brach ab."}])
		self.assertEqual(summary["first_errors"], [{"code": "", "text": "Der Lauf brach ab."}])

	def test_without_messages_there_is_nothing_to_show(self):
		self.assertEqual(
			messages.summary([]), {"errors": 0, "hints": 0, "first_errors": [], "first_hints": []}
		)

	def test_the_kinds_are_those_of_the_messages_of_a_transmission(self):
		fields = json.loads(MESSAGE_DOCTYPE.read_text(encoding="utf-8"))["fields"]
		(severity,) = (field for field in fields if field["fieldname"] == "severity")
		self.assertEqual(severity["options"].split("\n"), [ERROR, HINT])
