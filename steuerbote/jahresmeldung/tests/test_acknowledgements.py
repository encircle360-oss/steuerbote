"""The deliberate acknowledgement of a finding that holds a document back (steuerbote/jahresmeldung/acknowledgements.py):
per finding, with a reason, never for a finding that makes the file wrong by construction, and kept by Berechnen only
while the finding stays the same."""

from datetime import datetime
from unittest import TestCase

from steuerbote.jahresmeldung import acknowledgements
from steuerbote.jahresmeldung.acknowledgements import (
	AcknowledgementError,
	Ground,
	Problem,
	acknowledge,
	acknowledgeable,
	carried,
	ground_of,
	never,
	open_errors,
)
from steuerbote.jahresmeldung.findings import Finding, Severity, rows

ON = datetime(2027, 3, 1, 10, 30)
PROVISIONAL = Finding("KST-VORLAEUFIG", Severity.ERROR, "Die Vordrucke des Jahres sind vorläufig.")
UNBALANCED = Finding("JA-BILANZ-UNGLEICH", Severity.ERROR, "Aktiva und Passiva weichen voneinander ab.")
ERIC_RULE = Finding("170205010", Severity.ERROR, "Summe Aktiva ungleich Summe Passiva.", "bs.ass")
HINT = Finding("SB-UMSATZ", Severity.HINT, "Die Umsatzerlöse weichen ab.")


def row_of(finding: Finding, **fields) -> dict:
	(row,) = rows((finding,))
	return {**row, **fields}


class GroundTest(TestCase):
	"""What makes the file wrong by construction can never be acknowledged; everything else can, with a reason."""

	def test_an_error_of_a_rule_of_the_jahresdokumentation_is_never_acknowledged(self):
		"""„ein Datensatz, für den Hinweise aber keine Fehler gemeldet werden, [ist] valide“ (ERiC-Entwicklerhandbuch,
		Kap. 5.1.2.4.1): ERiC refuses a Datensatz with an error, whatever the company says."""
		self.assertIs(ground_of("170205010"), Ground.ERIC)
		self.assertIs(ground_of("30639"), Ground.ERIC)
		self.assertFalse(acknowledgeable("30639"))

	def test_a_balance_sheet_that_does_not_balance_or_is_incomplete_is_never_acknowledged(self):
		for code, ground in (
			("JA-BILANZ-UNGLEICH", Ground.NOT_BALANCED),
			("BILANZ-OHNE-PLATZ", Ground.INCOMPLETE),
			("EB-NICHT-ZUGEORDNET", Ground.INCOMPLETE),
			("JA-OHNE-POSTEN", Ground.INCOMPLETE),
			("EB-SUMME", Ground.STRUCTURE),
			("XBRL-MUSSFELD", Ground.STRUCTURE),
			("SB-NEU-BERECHNEN", Ground.STALE),
			("SB-ZUORDNUNG-VERSION", Ground.VERSION),
			("KST-NUTZDATEN", Ground.FILE),
			("KST-EBILANZ-ABWEICHUNG", Ground.RESULT),
		):
			with self.subTest(code=code):
				self.assertIs(ground_of(code), ground)
				self.assertFalse(acknowledgeable(code))

	def test_every_other_finding_of_steuerbote_is_acknowledged_with_a_reason(self):
		for code in ("KST-VORLAEUFIG", "KST-PRUEFUNG-FEHLT", "ZEITRAUM-FEHLT", "JA-RESTLAUFZEIT-FEHLT"):
			with self.subTest(code=code):
				self.assertIsNone(ground_of(code))
				self.assertTrue(acknowledgeable(code))

	def test_every_ground_names_its_source(self):
		self.assertEqual(set(acknowledgements.SOURCES), set(Ground))
		self.assertEqual(set(acknowledgements.NEVER.values()) | {Ground.ERIC}, set(Ground))
		for ground, source in acknowledgements.SOURCES.items():
			with self.subTest(ground=ground):
				self.assertTrue("§" in source or "Kap." in source or "Leitfaden" in source, source)

	def test_a_row_of_the_findings_says_whether_its_error_can_be_acknowledged(self):
		self.assertEqual(
			[row["acknowledgeable"] for row in rows((PROVISIONAL, UNBALANCED, ERIC_RULE, HINT))], [1, 0, 0, 0]
		)


class AcknowledgeTest(TestCase):
	def test_an_acknowledgement_names_its_reason_who_and_when(self):
		row = acknowledge(row_of(PROVISIONAL), " Mit der Steuerberatung abgestimmt. ", "kim@example.org", ON)
		self.assertEqual(
			(
				row["acknowledged"],
				row["acknowledgement_reason"],
				row["acknowledged_by"],
				row["acknowledged_on"],
			),
			(1, "Mit der Steuerberatung abgestimmt.", "kim@example.org", ON),
		)

	def test_an_empty_reason_withdraws_the_acknowledgement(self):
		row = acknowledge(row_of(PROVISIONAL), "Abgestimmt.", "kim@example.org", ON)
		withdrawn = acknowledge(row, "  ", "kim@example.org", ON)
		self.assertEqual(
			(
				withdrawn["acknowledged"],
				withdrawn["acknowledgement_reason"],
				withdrawn["acknowledged_by"],
				withdrawn["acknowledged_on"],
			),
			(0, None, None, None),
		)

	def test_refuses_a_finding_that_can_never_be_acknowledged_and_a_hint(self):
		for finding, problem in (
			(UNBALANCED, Problem.NEVER),
			(ERIC_RULE, Problem.NEVER),
			(HINT, Problem.NOT_AN_ERROR),
		):
			with self.subTest(code=finding.code), self.assertRaises(AcknowledgementError) as raised:
				acknowledge(row_of(finding), "Trotzdem.", "kim@example.org", ON)
			self.assertIs(raised.exception.problem, problem)
			self.assertEqual(raised.exception.code, finding.code)


class OpenErrorsTest(TestCase):
	def test_an_error_is_open_until_it_is_acknowledged(self):
		provisional = row_of(PROVISIONAL)
		acknowledged = acknowledge(provisional, "Abgestimmt.", "kim@example.org", ON)
		self.assertEqual(open_errors([provisional, row_of(HINT)]), (provisional,))
		self.assertEqual(open_errors([acknowledged, row_of(HINT)]), ())

	def test_an_acknowledgement_without_a_reason_counts_for_nothing(self):
		row = row_of(PROVISIONAL, acknowledged=1, acknowledgement_reason=" ")
		self.assertEqual(open_errors([row]), (row,))

	def test_a_finding_that_can_never_be_acknowledged_stays_open_even_when_marked(self):
		"""A row changed in the database by hand does not get around the ground."""
		row = row_of(UNBALANCED, acknowledged=1, acknowledgement_reason="Trotzdem.")
		self.assertEqual(open_errors([row]), (row,))
		self.assertEqual(never([row, row_of(PROVISIONAL)]), (row,))


class CarriedTest(TestCase):
	"""Berechnen writes the findings anew and keeps the acknowledgement of a finding that stays the same: the same code,
	reference and text. A finding whose amount or wording changed asks again."""

	def test_keeps_the_acknowledgement_of_the_same_finding(self):
		before = [acknowledge(row_of(PROVISIONAL), "Abgestimmt.", "kim@example.org", ON), row_of(HINT)]
		after = carried(rows((PROVISIONAL, HINT)), before)
		self.assertEqual(after[0]["acknowledgement_reason"], "Abgestimmt.")
		self.assertEqual(after[0]["acknowledged_by"], "kim@example.org")
		self.assertEqual(open_errors(after), ())
		self.assertNotIn("acknowledged", after[1])

	def test_a_finding_that_changed_asks_again(self):
		before = [acknowledge(row_of(PROVISIONAL), "Abgestimmt.", "kim@example.org", ON)]
		changed = Finding("KST-VORLAEUFIG", Severity.ERROR, "Die Vordrucke 2027 sind vorläufig.")
		after = carried(rows((changed,)), before)
		self.assertEqual(open_errors(after), tuple(after))

	def test_keeps_nothing_for_a_finding_that_can_never_be_acknowledged(self):
		before = [row_of(UNBALANCED, acknowledged=1, acknowledgement_reason="Trotzdem.")]
		after = carried(rows((UNBALANCED,)), before)
		self.assertNotIn("acknowledged", after[0])
