from enum import Enum
from unittest import TestCase

from steuerbote.jahresmeldung.findings import (
	DATA_LENGTH,
	Finding,
	FindingError,
	Severity,
	blocking,
	of_rows,
	ordered,
	ready,
	rows,
)

ERROR = Finding("30639", Severity.ERROR, "Die Steuer zu Kz 177 weicht um mehr als 1 Euro ab.", "E3003303")
HINT = Finding("SB-UMSATZ", Severity.HINT, "Die Umsatzerlöse weichen von Kz 81 ab.")


class ModuleSeverity(Enum):
	"""A severity of the core of a module, such as steuerbote.ustjahr.form.Severity."""

	ERROR = "Fehler"
	HINT = "Hinweis"


class FindingTest(TestCase):
	def test_names_its_code_severity_text_and_reference(self):
		self.assertEqual(
			(ERROR.code, ERROR.severity, ERROR.text, ERROR.reference),
			("30639", Severity.ERROR, "Die Steuer zu Kz 177 weicht um mehr als 1 Euro ab.", "E3003303"),
		)
		self.assertEqual(HINT.reference, "")

	def test_an_error_blocks_and_a_hint_does_not(self):
		"""The Regelart of a rule of the Jahresdokumentation: ERiC refuses a Fehler and notes a Hinweis."""
		self.assertTrue(ERROR.blocking)
		self.assertFalse(HINT.blocking)

	def test_the_severities_read_as_the_regelart_of_the_jahresdokumentation(self):
		self.assertEqual([severity.value for severity in Severity], ["Fehler", "Hinweis"])

	def test_takes_the_severity_of_a_module_by_its_value(self):
		finding = Finding("30002", ModuleSeverity.HINT, "Zeile 3 nur für eine berichtigte Erklärung.")
		self.assertIs(finding.severity, Severity.HINT)
		self.assertIs(Finding("30639", "Fehler", "Text").severity, Severity.ERROR)

	def test_refuses_a_severity_it_does_not_know(self):
		with self.assertRaises(FindingError):
			Finding("SB-X", "Warnung", "Text")

	def test_keeps_code_text_and_reference_without_blanks_at_either_end(self):
		finding = Finding(" SB-X ", Severity.HINT, "  Ein Hinweis. ", " Konto 8400 ")
		self.assertEqual(
			(finding.code, finding.text, finding.reference), ("SB-X", "Ein Hinweis.", "Konto 8400")
		)

	def test_needs_a_code_and_a_text(self):
		for code, text in (
			("", "Text"),
			("  ", "Text"),
			("SB-X", ""),
			("SB-X", " "),
			(None, "Text"),
			("SB-X", None),
		):
			with self.subTest(code=code, text=text), self.assertRaises(FindingError):
				Finding(code, Severity.HINT, text)

	def test_code_and_reference_fit_a_data_field(self):
		"""Frappe stores a Data field in 140 characters."""
		self.assertEqual(DATA_LENGTH, 140)
		Finding("C" * 140, Severity.HINT, "Text", "R" * 140)
		for code, reference in (("C" * 141, ""), ("SB-X", "R" * 141)):
			with self.subTest(code=len(code), reference=len(reference)), self.assertRaises(FindingError):
				Finding(code, Severity.HINT, "Text", reference)

	def test_a_reference_is_a_text(self):
		with self.assertRaises(FindingError):
			Finding("SB-X", Severity.HINT, "Text", None)


class ReadyTest(TestCase):
	def test_ready_without_a_blocking_finding_and_with_every_check_of_the_module_passed(self):
		self.assertTrue(ready(()))
		self.assertTrue(ready((HINT,)))
		self.assertTrue(ready((HINT,), True, True))

	def test_an_error_blocks_bereit(self):
		self.assertFalse(ready((HINT, ERROR)))

	def test_a_check_of_the_module_that_failed_blocks_bereit(self):
		self.assertFalse(ready((HINT,), True, False))

	def test_names_the_blocking_findings(self):
		self.assertEqual(blocking((HINT, ERROR, HINT)), (ERROR,))


class OrderTest(TestCase):
	def test_errors_come_first_then_hints_each_in_the_order_found(self):
		second = Finding("30640", Severity.ERROR, "Die Steuer zu Kz 178 weicht ab.")
		self.assertEqual(ordered((HINT, ERROR, second)), (ERROR, second, HINT))

	def test_names_a_finding_once(self):
		self.assertEqual(ordered((HINT, ERROR, HINT, ERROR)), (ERROR, HINT))


class RowsTest(TestCase):
	def test_a_row_of_the_table_befunde_per_finding(self):
		self.assertEqual(
			rows((HINT, ERROR)),
			[
				{
					"severity": "Fehler",
					"blocking": 1,
					"code": "30639",
					"text": "Die Steuer zu Kz 177 weicht um mehr als 1 Euro ab.",
					"reference": "E3003303",
				},
				{
					"severity": "Hinweis",
					"blocking": 0,
					"code": "SB-UMSATZ",
					"text": "Die Umsatzerlöse weichen von Kz 81 ab.",
					"reference": "",
				},
			],
		)

	def test_reads_the_rows_back(self):
		stored = [
			{**row, "name": f"row-{index}", "idx": index} for index, row in enumerate(rows((ERROR, HINT)))
		]
		self.assertEqual(of_rows(stored), (ERROR, HINT))

	def test_reads_a_row_without_a_reference(self):
		self.assertEqual(
			of_rows([{"severity": "Hinweis", "code": "SB-UMSATZ", "text": HINT.text, "reference": None}]),
			(HINT,),
		)
