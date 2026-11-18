import json
from unittest import TestCase

from steuerbote.eric.result import (
	ERROR,
	HINT,
	TESTMERKER,
	Message,
	Operation,
	Outcome,
	TransmissionResult,
)

PDF = b"%PDF-1.4\n\x00\x01binary\n%%EOF\n"


def accepted_send(**changes) -> TransmissionResult:
	fields = {
		"operation": Operation.SEND,
		"ok": True,
		"simulated": False,
		"eric_version": "44.3.6.0",
		"transferticket": "et0stub0accepted0000000000000001",
		"testmerker": None,
		"messages": (Message("0", "Daten wurden erfolgreich angenommen.", HINT),),
		"protocol_pdf": PDF,
		"server_response_xml": "<Elster/>",
		"outcome": Outcome.ACCEPTED,
	}
	return TransmissionResult(**(fields | changes))


class OperationTest(TestCase):
	def test_values_name_the_operations(self):
		self.assertEqual([operation.value for operation in Operation], ["validate", "test_send", "send"])

	def test_only_the_send_operations_send(self):
		self.assertEqual([operation.sends for operation in Operation], [False, True, True])


class OutcomeTest(TestCase):
	def test_only_valid_and_accepted_are_ok(self):
		self.assertEqual({outcome for outcome in Outcome if outcome.ok}, {Outcome.VALID, Outcome.ACCEPTED})


class MessageTest(TestCase):
	def test_field_is_optional(self):
		self.assertIsNone(Message("110085064", "Die Kennzahl 83 fehlt.", ERROR).field)

	def test_refuses_an_unknown_severity(self):
		with self.assertRaises(ValueError):
			Message("1", "Text", "warning")


class TransmissionResultTest(TestCase):
	def test_testmerker_is_the_one_the_server_deletes_on_receipt(self):
		self.assertEqual(TESTMERKER, "700000004")

	def test_derives_the_outcome_from_ok_and_the_operation(self):
		self.assertIs(
			TransmissionResult(Operation.VALIDATE, True, True, "simulation", None, None).outcome,
			Outcome.VALID,
		)
		self.assertIs(
			TransmissionResult(Operation.TEST_SEND, True, True, "simulation", "SIM-1", TESTMERKER).outcome,
			Outcome.ACCEPTED,
		)
		self.assertIs(
			TransmissionResult(Operation.SEND, False, False, "44.3.6.0", None, None).outcome, Outcome.FAILED
		)

	def test_keeps_messages_as_a_tuple(self):
		result = accepted_send(messages=[Message("0", "Angenommen", HINT)])
		self.assertEqual(result.messages, (Message("0", "Angenommen", HINT),))

	def test_ok_must_match_the_outcome(self):
		with self.assertRaises(ValueError):
			accepted_send(ok=False)
		with self.assertRaises(ValueError):
			accepted_send(ok=True, outcome=Outcome.UNKNOWN)

	def test_a_validation_neither_reaches_the_server_nor_has_a_ticket(self):
		for outcome in (Outcome.ACCEPTED, Outcome.REJECTED, Outcome.UNKNOWN):
			with self.subTest(outcome=outcome), self.assertRaises(ValueError):
				TransmissionResult(
					Operation.VALIDATE, outcome.ok, False, "44.3.6.0", None, None, outcome=outcome
				)
		with self.assertRaises(ValueError):
			TransmissionResult(Operation.VALIDATE, True, False, "44.3.6.0", "et0", None)

	def test_testmerker_belongs_to_the_test_send_only(self):
		with self.assertRaises(ValueError):
			accepted_send(testmerker=TESTMERKER)
		with self.assertRaises(ValueError):
			accepted_send(operation=Operation.TEST_SEND, testmerker=None)
		self.assertEqual(
			accepted_send(operation=Operation.TEST_SEND, testmerker=TESTMERKER).testmerker, TESTMERKER
		)

	def test_converts_to_json_with_the_pdf_in_base64(self):
		data = accepted_send().to_dict()
		self.assertEqual(
			data,
			{
				"operation": "send",
				"ok": True,
				"outcome": "accepted",
				"simulated": False,
				"eric_version": "44.3.6.0",
				"transferticket": "et0stub0accepted0000000000000001",
				"testmerker": None,
				"messages": [
					{
						"code": "0",
						"text": "Daten wurden erfolgreich angenommen.",
						"severity": "hint",
						"field": None,
					}
				],
				"protocol_pdf": "JVBERi0xLjQKAAFiaW5hcnkKJSVFT0YK",
				"server_response_xml": "<Elster/>",
			},
		)
		self.assertEqual(json.loads(json.dumps(data)), data)

	def test_reads_back_what_it_wrote(self):
		for result in (
			accepted_send(),
			accepted_send(protocol_pdf=None, server_response_xml=None, messages=()),
			TransmissionResult(
				Operation.VALIDATE,
				False,
				True,
				"simulation",
				None,
				None,
				(Message("SIM-003", "Kz83 fehlt", ERROR, "Kz83"),),
				outcome=Outcome.INVALID,
			),
		):
			with self.subTest(result=result):
				self.assertEqual(
					TransmissionResult.from_dict(json.loads(json.dumps(result.to_dict()))), result
				)

	def test_refuses_data_of_the_wrong_shape(self):
		valid = accepted_send().to_dict()
		broken = {
			"no mapping": [],
			"unknown operation": valid | {"operation": "print"},
			"ok as text": valid | {"ok": "yes"},
			"simulated missing": {key: value for key, value in valid.items() if key != "simulated"},
			"version as number": valid | {"eric_version": 44},
			"ticket as number": valid | {"transferticket": 1},
			"messages as text": valid | {"messages": "none"},
			"message as text": valid | {"messages": ["0"]},
			"message code as number": valid | {"messages": [{"code": 0, "text": "", "severity": "hint"}]},
			"message field as number": valid
			| {"messages": [{"code": "0", "text": "", "severity": "hint", "field": 83}]},
			"pdf not base64": valid | {"protocol_pdf": "no base64!"},
			"unknown outcome": valid | {"outcome": "lost"},
			"inconsistent": valid | {"ok": False},
		}
		for case, data in broken.items():
			with self.subTest(case), self.assertRaises(ValueError):
				TransmissionResult.from_dict(data)
