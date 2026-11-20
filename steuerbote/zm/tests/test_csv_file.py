from unittest import TestCase

from steuerbote.zm.csv_file import (
	EXCEL_VERSION,
	HEADER,
	MAX_ROWS,
	VERSION,
	csv_file,
)
from steuerbote.zm.errors import ZmError
from steuerbote.zm.lines import Art, Meldezeile
from steuerbote.zm.tests.support import AUSTRIA, FRANCE, d

# „Beispielhafte CSV-Datei“ of the ELSTER help „Import von Meldelisten zur Zusammenfassenden Meldung“,
# https://www.elster.de/eportal/helpGlobal?themaGlobal=zmdo_import_eop, read on 2026-11-20. The page shows the
# lines separated by line feeds and nothing after the last line.
HELP_PAGE_EXAMPLE = """#v3.0
#ve3.2.1
Umsatzsteuer-Identifikationsnummer (USt-IdNr.),Summe (Euro),Art der Leistung
FRWL247100014,12345678911,L
HR12345678903,-12345678911,D
HR12345678900,2000,S
IE8Z49289F,1,D
IE3628739L,2,L
IE3628739UA,3,S
IE4769510A,3,D
IE8285018I,3,D
BG0101010007,4,D
EE100217418,5,L
ESW0068209F,7,D
IT00000008888,8,L
IT00000009993,6,S
BE1082047173,6,S"""


def rows_of(text: str) -> list[Meldezeile]:
	rows = []
	for line in text.split("\n")[3:]:
		vat_id, amount, art = line.split(",")
		rows.append(Meldezeile(vat_id, Art(art), d(amount)))
	return rows


class CsvFileTest(TestCase):
	def test_the_example_of_the_help_page_byte_for_byte(self):
		self.assertEqual(csv_file(rows_of(HELP_PAGE_EXAMPLE)), HELP_PAGE_EXAMPLE.encode("utf-8"))

	def test_version_lines_and_header(self):
		"""Versionstabelle of the help page: CSV version 3.0, Excel version 3.2.1. „1. Zeile: Neueste CSV-Version
		der Importfunktion mit dem Präfix #v“ (ELSTER, Allgemeine Anleitung zur Erstellung von CSV-Dateien)."""
		self.assertEqual((VERSION, EXCEL_VERSION), ("#v3.0", "#ve3.2.1"))
		self.assertEqual(
			HEADER, "Umsatzsteuer-Identifikationsnummer (USt-IdNr.),Summe (Euro),Art der Leistung"
		)
		content = csv_file([Meldezeile(AUSTRIA, Art.L, d("1000"))])
		self.assertEqual(
			content.split(b"\n"), [b"#v3.0", b"#ve3.2.1", HEADER.encode(), b"ATU12345678,1000,L"]
		)

	def test_utf_8_without_byte_order_mark(self):
		"""„Sie können sowohl "UTF-8" als auch "UTF-8 mit BOM" als Encoding verwenden.“ (ELSTER, Hilfe zur
		UTF-8-Umstellung der Importfunktion)"""
		content = csv_file([Meldezeile(AUSTRIA, Art.L, d("1"))])
		self.assertFalse(content.startswith(b"\xef\xbb\xbf"))
		content.decode("utf-8")

	def test_amounts_are_integers_without_cents(self):
		content = csv_file([Meldezeile(AUSTRIA, Art.L, d("1000.00")), Meldezeile(FRANCE, Art.S, d("-25"))])
		self.assertEqual(content.split(b"\n")[3:], [b"ATU12345678,1000,L", b"FR12345678901,-25,S"])

	def test_at_most_eleven_digits(self):
		"""Datensatztabelle Meldezeilen: „Die Anzahl der Ziffern darf nicht größer als 11 sein, mit dem negativen
		Vorzeichen 12.“"""
		csv_file([Meldezeile(AUSTRIA, Art.L, d("-99999999999"))])
		with self.assertRaisesRegex(ZmError, "more than 11 digits"):
			csv_file([Meldezeile(AUSTRIA, Art.L, d("100000000000"))])

	def test_at_most_1500_rows(self):
		"""„Es können maximal 1500 Datenzeilen in einer CSV-Datei importiert werden.“"""
		rows = [Meldezeile(f"ATU{number:08d}", Art.L, d("1")) for number in range(MAX_ROWS + 1)]
		self.assertEqual(MAX_ROWS, 1500)
		self.assertEqual(csv_file(rows[:MAX_ROWS]).count(b"\n"), MAX_ROWS + 2)
		with self.assertRaisesRegex(
			ZmError, "1501 Meldezeilen; the import of Mein ELSTER takes at most 1500"
		):
			csv_file(rows)

	def test_at_least_one_row(self):
		"""ZMDO rule 170045002: „Es wurden keine Meldezeilen angegeben. Bitte beachten Sie, dass Nullmeldungen
		nicht zulässig sind.“"""
		with self.assertRaisesRegex(ZmError, "at least one Meldezeile"):
			csv_file([])

	def test_zero_only_in_a_correction(self):
		"""ZMDO rule 170045001 refuses a zero line in a first ZM; a correction cancels a line with „0“."""
		zero = [Meldezeile(AUSTRIA, Art.L, d("0"))]
		with self.assertRaisesRegex(ZmError, "reports 0 euros"):
			csv_file(zero)
		self.assertTrue(csv_file(zero, correction=True).endswith(b"\nATU12345678,0,L"))

	def test_each_line_once(self):
		"""ZMDO rules 170045003 to 170045005: „Bitte addieren Sie die Beträge.“"""
		with self.assertRaisesRegex(ZmError, "appears twice"):
			csv_file([Meldezeile(AUSTRIA, Art.L, d("1")), Meldezeile(AUSTRIA, Art.L, d("2"))])
		csv_file([Meldezeile(AUSTRIA, Art.L, d("1")), Meldezeile(AUSTRIA, Art.S, d("2"))])
