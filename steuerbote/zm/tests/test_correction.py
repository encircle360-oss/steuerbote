from unittest import TestCase

from steuerbote.zm.correction import Correction, as_filed, correct
from steuerbote.zm.errors import ZmError
from steuerbote.zm.lines import Art, Meldezeile
from steuerbote.zm.period import ReportingPeriod
from steuerbote.zm.tests.support import d

# The examples of BZSt „Berichtigung einer ZM“ all concern the Spanish Unternehmer P.
P = "ES111111112"
WRONG = "ES111111113"
FRANCE_OTHER = "FR98765432101"
MARCH = ReportingPeriod.month(2026, 3)
FEBRUARY = ReportingPeriod.month(2026, 2)


def line(vat_id: str, art: Art, amount: str) -> Meldezeile:
	return Meldezeile(vat_id, art, d(amount))


class CorrectionCasesTest(TestCase):
	"""BZSt „Berichtigung einer ZM“, „Was und wie ist zu berichtigen?“, cases 1 to 5, and the Anleitung zur ZM,
	IV.12: „In der Berichtigungsmeldung werden die Angaben, die in der ursprünglichen ZM korrekt gemeldet worden
	sind, nicht wiederholt.“"""

	def test_1_incomplete_zm(self):
		"""„In dieser erklärt er nur die fehlende innergemeinschaftliche Lieferung an P“."""
		filed = as_filed([line(FRANCE_OTHER, Art.L, "700")])
		result = correct(MARCH, filed, [line(FRANCE_OTHER, Art.L, "700"), line(P, Art.L, "5000")])
		self.assertEqual(result, Correction(MARCH, (line(P, Art.L, "5000"),)))

	def test_2_wrong_meldezeitraum(self):
		"""„Für den 2. Kalendermonat hat M eine berichtigte ZM abzugeben. In dieser trägt er den gemeldeten Umsatz
		mit der Summe der Bemessungsgrundlage „0“ ein. Des Weiteren ist eine ZM für den 3. Kalendermonat
		abzugeben.“"""
		february = correct(FEBRUARY, as_filed([line(P, Art.L, "13000")]), [])
		self.assertEqual(february.lines, (line(P, Art.L, "0"),))
		march = correct(MARCH, as_filed([]), [line(P, Art.L, "13000")])
		self.assertEqual(march.lines, (line(P, Art.L, "13000"),))

	def test_3_wrong_foreign_vat_id(self):
		"""„für die Stornierung den gemeldeten Umsatz mit der nicht korrekten USt-IdNr. ES111111113 mit der Summe der
		Bemessungsgrundlage „0“ UND den getätigten Umsatz mit der korrekten USt-IdNr. ES111111112“."""
		result = correct(MARCH, as_filed([line(WRONG, Art.L, "21000")]), [line(P, Art.L, "21000")])
		self.assertEqual(result.lines, (line(WRONG, Art.L, "0"), line(P, Art.L, "21000")))

	def test_4_wrong_sum(self):
		"""„In dieser trägt er eine Meldezeile mit der korrekten Summe der Bemessungsgrundlage (20.000 €) ein.“
		Anleitung zur ZM, IV.12.2: „Es ist also nicht nur der zu viel oder zu wenig gemeldete Differenzbetrag
		anzugeben!“"""
		result = correct(MARCH, as_filed([line(P, Art.L, "30000")]), [line(P, Art.L, "20000")])
		self.assertEqual(result.lines, (line(P, Art.L, "20000"),))

	def test_5_wrong_art(self):
		"""„für die Stornierung den gemeldeten Umsatz unter Angabe der Summe der Bemessungsgrundlage „0“ [...] sonstige
		Leistung [...] UND den getätigten Umsatz [...] innergemeinschaftliche Lieferung“."""
		result = correct(MARCH, as_filed([line(P, Art.S, "20000")]), [line(P, Art.L, "20000")])
		self.assertEqual(result.lines, (line(P, Art.S, "0"), line(P, Art.L, "20000")))


class AsFiledTest(TestCase):
	def test_a_later_correction_replaces_the_amount_of_its_lines(self):
		original = [line(P, Art.L, "30000"), line(FRANCE_OTHER, Art.S, "800")]
		first_correction = [line(P, Art.L, "20000")]
		second_correction = [line(FRANCE_OTHER, Art.S, "0")]
		self.assertEqual(
			as_filed(original, first_correction, second_correction),
			{(P, Art.L): d("20000"), (FRANCE_OTHER, Art.S): d("0")},
		)

	def test_a_cancelled_line_is_not_cancelled_again(self):
		filed = as_filed([line(P, Art.L, "30000")], [line(P, Art.L, "0")])
		self.assertEqual(correct(MARCH, filed, []).lines, ())

	def test_a_cancelled_line_can_come_back(self):
		filed = as_filed([line(P, Art.L, "30000")], [line(P, Art.L, "0")])
		self.assertEqual(correct(MARCH, filed, [line(P, Art.L, "30000")]).lines, (line(P, Art.L, "30000"),))

	def test_one_zm_holds_a_line_once(self):
		with self.assertRaisesRegex(ZmError, "twice"):
			as_filed([line(P, Art.L, "1"), line(P, Art.L, "2")])
		with self.assertRaisesRegex(ZmError, "twice"):
			correct(MARCH, {}, [line(P, Art.L, "1"), line(P, Art.L, "2")])


class NotACorrectionTest(TestCase):
	def test_nothing_changed(self):
		filed = as_filed([line(P, Art.L, "20000")])
		self.assertEqual(correct(MARCH, filed, [line(P, Art.L, "20000.00")]).lines, ())

	def test_a_correction_refers_to_the_meldezeitraum_it_corrects(self):
		"""„Für jeden zu berichtigenden Meldezeitraum ist eine gesonderte berichtigte ZM elektronisch zu
		übermitteln.“"""
		self.assertEqual(correct(FEBRUARY, {}, [line(P, Art.L, "1")]).period, FEBRUARY)
