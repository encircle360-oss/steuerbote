"""The table of elements in docs/abgabe-mein-elster.md shows what ustva_xml.py writes."""

from pathlib import Path
from unittest import TestCase

from steuerbote.elster.ustva_xml import SCHEMAS
from steuerbote.ustva import catalogue_for

DOC = Path(__file__).resolve().parents[3] / "docs" / "abgabe-mein-elster.md"


def rows(heading: str) -> list[list[str]]:
	"""The cells of each row of the table under the heading, without its head."""
	text = DOC.read_text(encoding="utf-8")
	start = text.index(f"\n## {heading}\n")
	end = text.find("\n## ", start + 1)
	lines = [line for line in text[start:end].splitlines() if line.startswith("|")]
	return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines[2:]]


class ElementTableTest(TestCase):
	def setUp(self):
		self.rows = rows("Kennzahlen und Elemente")
		self.schema = SCHEMAS[2026]

	def test_lists_the_elements_in_the_order_of_the_schema(self):
		self.assertEqual(tuple(row[1].strip("`") for row in self.rows), self.schema.elements)
		self.assertEqual(
			[row[0] for row in self.rows], [str(number) for number in range(1, len(self.rows) + 1)]
		)

	def test_names_the_line_of_each_kennzahl_on_the_form(self):
		catalogue = catalogue_for(2026)
		for row in self.rows:
			kennzahl = catalogue.get(row[1].strip("`").removeprefix("Kz"))
			if kennzahl is not None:
				with self.subTest(kennzahl=kennzahl.number):
					self.assertEqual(row[2], str(kennzahl.line))

	def test_marks_the_kennzahlen_without_sign(self):
		for row in self.rows:
			with self.subTest(element=row[1]):
				number = row[1].strip("`").removeprefix("Kz")
				self.assertEqual("ohne Vorzeichen" in row[3], number in self.schema.unsigned)
