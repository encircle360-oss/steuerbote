from unittest import TestCase

from steuerbote.vatid.exemption import KENNZAHLEN, consequence


class ConsequenceTest(TestCase):
	def test_names_what_a_missing_or_invalid_vat_id_costs_per_kennzahl(self):
		"""The Voranmeldung and the Zusammenfassende Meldung say the same sentence about the same voucher."""
		self.assertEqual(
			consequence("41"),
			"Ohne gültige USt-IdNr. des Abnehmers ist die innergemeinschaftliche Lieferung nicht steuerfrei "
			"(§ 6a Abs. 1 Satz 1 Nr. 4 UStG); ohne richtige Zeile in der ZM entfällt die Steuerfreiheit ebenso "
			"(§ 4 Nr. 1 Buchst. b UStG).",
		)
		self.assertEqual(
			consequence("42"),
			"Ohne gültige USt-IdNr. des letzten Abnehmers kann die ZM die Lieferung im Dreiecksgeschäft nicht "
			"melden (§ 18a Abs. 7 Satz 1 Nr. 4 UStG).",
		)
		self.assertEqual(
			consequence("21"),
			"Ohne gültige USt-IdNr. des Leistungsempfängers fehlt der Nachweis, dass er Unternehmer ist "
			"(§ 3a Abs. 2 UStG, UStAE 3a.2 Abs. 9), und die ZM kann die Leistung nicht melden "
			"(§ 18a Abs. 7 Satz 1 Nr. 3 UStG).",
		)

	def test_knows_the_kennzahlen_of_the_zm_only(self):
		self.assertEqual(KENNZAHLEN, ("41", "42", "21"))
		with self.assertRaisesRegex(ValueError, "81"):
			consequence("81")
