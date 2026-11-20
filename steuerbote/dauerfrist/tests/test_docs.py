"""The table of fields in docs/dauerfristverlaengerung.md shows the layout of form.py."""

from pathlib import Path
from unittest import TestCase

from steuerbote.dauerfrist.form import Context, layout_for

DOC = Path(__file__).resolve().parents[3] / "docs" / "dauerfristverlaengerung.md"
DF = Context.DAUERFRISTVERLAENGERUNG
SVZ = Context.UMSATZSTEUERSONDERVORAUSZAHLUNG
YES = "ja"


def rows(heading: str) -> list[list[str]]:
	"""The cells of each row of the table under the heading, without its head."""
	text = DOC.read_text(encoding="utf-8")
	start = text.index(f"\n## {heading}\n")
	end = text.find("\n## ", start + 1)
	lines = [line for line in text[start:end].splitlines() if line.startswith("|")]
	return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines[2:]]


class FieldTableTest(TestCase):
	def setUp(self):
		self.rows = rows("Vordruck USt 1 H in ELSTER")
		self.layout = layout_for(2026)

	def test_lists_the_elements_in_the_order_of_the_schema(self):
		self.assertEqual(tuple(row[0].strip("`") for row in self.rows), self.layout.elements(SVZ))

	def test_names_the_line_of_each_field_on_the_form(self):
		for row in self.rows:
			field = self.layout.field(SVZ, row[0].strip("`"))
			with self.subTest(element=field.element):
				self.assertEqual(row[1], "" if field.line is None else str(field.line))

	def test_marks_the_fields_of_each_context(self):
		for row in self.rows:
			element = row[0].strip("`")
			with self.subTest(element=element):
				self.assertEqual(row[2] == YES, element in self.layout.elements(DF))
				self.assertEqual(row[3], YES)
