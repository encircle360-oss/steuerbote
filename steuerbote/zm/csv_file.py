"""The CSV file that imports the lines of a Zusammenfassende Meldung into the online form of Mein ELSTER.

The form „Zusammenfassende Meldung“ of Mein ELSTER and of the BZSt-Online-Portal takes the Meldezeilen from a CSV
file (BZSt, „Elektronische Abgabe und Datenübermittlung“). The ELSTER help „Import von Meldelisten zur
Zusammenfassenden Meldung“ gives the record (Datensatztabelle Meldezeilen, Satzart 1) and an example, and the
„Allgemeine Anleitung zur Erstellung von CSV-Dateien für die Importfunktion“ the rules of every import:

- the first line is the newest CSV version with the prefix #v, 3.0 in the Versionstabelle; the example follows it
  with the Excel version of the same table, #ve3.2.1, which the general rules do not mention, and Steuerbote
  writes the file as the example does;
- then the column header, then one line per Meldezeile: USt-IdNr. (AN 7 to 14), Summe (Euro) as a whole number
  of at most 11 digits, 12 with the minus sign, and the Art D, L or S;
- one separator in the whole file, the example's comma; no empty lines; UTF-8, „Sie können sowohl "UTF-8" als
  auch "UTF-8 mit BOM" als Encoding verwenden“ (ELSTER, Hilfe zur UTF-8-Umstellung der Importfunktion);
- „Es können maximal 1500 Datenzeilen in einer CSV-Datei importiert werden“, and the form itself takes at most
  1,500 Meldezeilen (BZSt, „Elektronische Abgabe und Datenübermittlung“).

The example separates its lines by line feeds and ends without one; Steuerbote writes the same bytes. The ERiC data
type ZMDO adds two rules the file keeps as well: no Meldezeile twice („Bitte addieren Sie die Beträge“, rules
170045003 to 170045005) and none of 0 euros in a first ZM (170045001, 170045002); a berichtigte ZM cancels a line
with 0 (BZSt, „Berichtigung einer ZM“).
"""

from collections.abc import Iterable

from steuerbote.zm.errors import ZmError
from steuerbote.zm.lines import Meldezeile

VERSION = "#v3.0"
EXCEL_VERSION = "#ve3.2.1"
HEADER = "Umsatzsteuer-Identifikationsnummer (USt-IdNr.),Summe (Euro),Art der Leistung"
SEPARATOR = ","
LINE_BREAK = "\n"
ENCODING = "utf-8"
MAX_ROWS = 1500
MAX_DIGITS = 11

NO_ROWS = "A Zusammenfassende Meldung needs at least one Meldezeile."
TOO_MANY_ROWS = (
	"The Zusammenfassende Meldung has {0} Meldezeilen; the import of Mein ELSTER takes at most {1}."
)
ZERO_ROW = "The Meldezeile {0} {1} reports 0 euros, which only a berichtigte Zusammenfassende Meldung may do."
ROW_TWICE = "The Meldezeile {0} {1} appears twice; its amounts belong in one line."
TOO_MANY_DIGITS = "The sum {2} of the Meldezeile {0} {1} has more than 11 digits."


def csv_file(rows: Iterable[Meldezeile], correction: bool = False) -> bytes:
	"""The file for the import of Mein ELSTER, with the Meldezeilen in the order given.

	``correction`` for a berichtigte ZM, whose lines may cancel a filed line with 0.
	"""
	rows = list(rows)
	if not rows:
		raise ZmError(NO_ROWS)
	if len(rows) > MAX_ROWS:
		raise ZmError(TOO_MANY_ROWS, len(rows), MAX_ROWS)
	seen: set[tuple[str, str]] = set()
	lines = [VERSION, EXCEL_VERSION, HEADER]
	for row in rows:
		key = (row.vat_id, row.art.value)
		if key in seen:
			raise ZmError(ROW_TWICE, *key)
		seen.add(key)
		amount = int(row.amount)
		if not amount and not correction:
			raise ZmError(ZERO_ROW, *key)
		if len(str(abs(amount))) > MAX_DIGITS:
			raise ZmError(TOO_MANY_DIGITS, *key, amount)
		lines.append(SEPARATOR.join((row.vat_id, str(amount), row.art.value)))
	return LINE_BREAK.join(lines).encode(ENCODING)
