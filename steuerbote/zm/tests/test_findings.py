from unittest import TestCase

from steuerbote.zm.findings import BLOCKING, Code, Finding, Severity, voucher_no


class FindingTest(TestCase):
	def test_every_code_blocks_or_hints(self):
		for code in Code:
			with self.subTest(code):
				expected = Severity.ERROR if code in BLOCKING else Severity.HINT
				self.assertIs(Finding(code, "Text.").severity, expected)

	def test_only_the_comparison_the_filed_returns_and_the_lines_by_hand_give_hints(self):
		hints = {code for code in Code if not Finding(code, "Text.").blocking}
		self.assertEqual(hints, {Code.FILED_RETURNS, Code.PREVIOUS_PERIOD, Code.OWN_LINE})

	def test_codes_are_distinct_from_those_of_the_voranmeldung(self):
		self.assertTrue(all(code.value.startswith("ZM-") for code in Code))

	def test_a_sentence_names_the_voucher_without_its_type(self):
		self.assertEqual(voucher_no("Sales Invoice:SINV-0001"), "SINV-0001")
		self.assertEqual(voucher_no("SINV-0001"), "SINV-0001")
		self.assertEqual(voucher_no(None), "")
