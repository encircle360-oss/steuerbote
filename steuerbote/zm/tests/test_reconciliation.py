from unittest import TestCase

from steuerbote.steuerbote.report.ustva_kennzahlen.attribution import Contribution
from steuerbote.zm.findings import Code
from steuerbote.zm.lines import Art, Override, build
from steuerbote.zm.reconciliation import Filed, reconcile
from steuerbote.zm.tests.support import AUSTRIA, FIGURES, FRANCE, SPAIN, d, invoice


def share(voucher: str | None, kennzahl: str, amount: str) -> Contribution:
	"""What the report „UStVA Kennzahlen“ finds behind a Kennzahl, as the Frappe layer passes it."""
	return Contribution(kennzahl, voucher, ("8125",), d("0"), d(amount), d(amount))


def statement(*amounts, overrides=None):
	return build(amounts, FIGURES, overrides=overrides)


class LedgerTest(TestCase):
	"""ΣL = Kz 41, ΣD = Kz 42 and ΣS = Kz 21 over the same months: § 18a Absatz 7 and 8 UStG and § 18b UStG
	report the same turnover in both, and the BZSt compares them: „Nach Eingang der ZM beim BZSt erfolgt ein
	Abgleich der gemeldeten innergemeinschaftlichen Umsatzarten mit den Angaben in den
	Umsatzsteuer-Voranmeldungen und -Jahreserklärungen.“ (BZSt, „Berichtigung einer ZM“)"""

	def test_balanced_when_every_voucher_matches(self):
		zm = statement(
			invoice("SINV-1", "1000.50"),
			invoice("SINV-2", "300.00", kennzahl="42", vat_id=FRANCE, destination="FR"),
			invoice("SINV-3", "200.00", kennzahl="21", vat_id=SPAIN),
		)
		ledger = [
			share("Sales Invoice:SINV-1", "41", "1000.50"),
			share("Sales Invoice:SINV-2", "42", "300.00"),
			share("Sales Invoice:SINV-3", "21", "200.00"),
			share("Sales Invoice:SINV-4", "81", "999.00"),
		]
		result = reconcile(zm, ledger, FIGURES)
		self.assertTrue(result.balanced)
		self.assertEqual(
			[(row.art, row.kennzahl, row.ledger, row.statement, row.reported) for row in result.rows],
			[
				(Art.L, "41", d("1000.50"), d("1000.50"), d("1000")),
				(Art.D, "42", d("300.00"), d("300.00"), d("300")),
				(Art.S, "21", d("200.00"), d("200.00"), d("200")),
			],
		)
		self.assertEqual(result.findings, ())

	def test_a_difference_names_its_vouchers(self):
		zm = statement(invoice("SINV-1", "1000.00"), invoice("SINV-9", "50.00"))
		ledger = [
			share("Sales Invoice:SINV-1", "41", "1200.00"),
			share("Sales Invoice:SINV-2", "41", "80.00"),
		]
		result = reconcile(zm, ledger, FIGURES)
		row = result.rows[0]
		self.assertFalse(result.balanced)
		self.assertEqual(
			(row.ledger, row.statement, row.difference), (d("1280.00"), d("1050.00"), d("-230.00"))
		)
		self.assertEqual(
			[(item.voucher, item.ledger, item.statement, item.difference) for item in row.differences],
			[
				("Sales Invoice:SINV-1", d("1200.00"), d("1000.00"), d("-200.00")),
				("Sales Invoice:SINV-2", d("80.00"), d("0"), d("-80.00")),
				("Sales Invoice:SINV-9", d("0"), d("50.00"), d("50.00")),
			],
		)
		self.assertEqual([finding.code for finding in result.findings], [Code.LEDGER] * 3)
		self.assertTrue(all(finding.blocking for finding in result.findings))
		self.assertEqual(
			[(finding.voucher, finding.text) for finding in result.findings],
			[
				(
					"Sales Invoice:SINV-1",
					"Beleg SINV-1 geht laut Hauptbuch mit 1.200,00 € in Kz 41 ein, in die ZM mit 1.000,00 €.",
				),
				(
					"Sales Invoice:SINV-2",
					"Beleg SINV-2 geht laut Hauptbuch mit 80,00 € in Kz 41 ein, in die ZM mit 0,00 €.",
				),
				(
					"Sales Invoice:SINV-9",
					"Beleg SINV-9 geht laut Hauptbuch mit 0,00 € in Kz 41 ein, in die ZM mit 50,00 €.",
				),
			],
		)

	def test_postings_without_a_voucher(self):
		result = reconcile(statement(), [share(None, "21", "10.00")], FIGURES)
		self.assertEqual(
			result.findings[0].text,
			"Buchungen ohne Beleg gehen laut Hauptbuch mit 10,00 € in Kz 21 ein, in die ZM mit 0,00 €.",
		)

	def test_lines_the_zm_cannot_report_still_reconcile(self):
		"""A voucher without USt-IdNr. is a line of its own that holds the ZM back; the ledger and the vouchers of
		the ZM still agree."""
		zm = statement(invoice("JV-1", "500.00", party=None, vat_id=None, voucher_type="Journal Entry"))
		result = reconcile(zm, [share("Journal Entry:JV-1", "41", "500.00")], FIGURES)
		self.assertTrue(result.balanced)
		self.assertEqual(result.rows[0].reported, d("0"))


class FiledReturnsTest(TestCase):
	"""The Meldezeilen against the Kz 41, 42 and 21 of the Voranmeldungen filed for the same months. Every line
	and every Voranmeldung drops less than a euro, so a difference that large or larger is no rounding; it gets a
	hint and holds nothing back."""

	def test_rounding_explains_less_than_a_euro_per_line_and_return(self):
		zm = statement(
			invoice("1", "100.60", vat_id=AUSTRIA),
			invoice("2", "100.60", vat_id=FRANCE),
			invoice("3", "0.60", vat_id=SPAIN),
		)
		ledger = [
			share(f"Sales Invoice:{n}", "41", amount)
			for n, amount in (("1", "100.60"), ("2", "100.60"), ("3", "0.60"))
		]
		# Kz 41 of one Voranmeldung: 201.80 drops to 201; the lines report 100 + 100 + 0.
		result = reconcile(zm, ledger, FIGURES, filed={"41": Filed(d("201"), 1)})
		self.assertEqual((result.rows[0].reported, result.rows[0].filed), (d("200"), d("201")))
		self.assertEqual(result.findings, ())

	def test_a_larger_difference_gets_a_hint(self):
		zm = statement(
			invoice("1", "1000.00"), overrides={(AUSTRIA, Art.L): Override(d("900"), "Gutschrift folgt")}
		)
		result = reconcile(
			zm, [share("Sales Invoice:1", "41", "1000.00")], FIGURES, filed={"41": Filed(d("1000"), 1)}
		)
		self.assertTrue(result.balanced)
		self.assertEqual([finding.code for finding in result.findings], [Code.FILED_RETURNS])
		self.assertFalse(result.findings[0].blocking)
		self.assertEqual(
			result.findings[0].text,
			"Die abgegebenen Voranmeldungen melden in Kz 41 1.000,00 €, die Zeilen L der ZM 900,00 €.",
		)

	def test_only_the_kennzahlen_given(self):
		result = reconcile(
			statement(invoice("1", "10.00")),
			[share("Sales Invoice:1", "41", "10.00")],
			FIGURES,
			filed={"21": Filed(d("0"), 3)},
		)
		self.assertEqual([row.filed for row in result.rows], [None, None, d("0")])
		self.assertEqual(result.findings, ())

	def test_filed_amounts_are_whole_euros_of_at_least_one_return(self):
		with self.assertRaises(ValueError):
			Filed(d("10.50"), 1)
		with self.assertRaises(ValueError):
			Filed(d("10"), 0)
