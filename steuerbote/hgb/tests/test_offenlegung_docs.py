"""docs/offenlegung.md shows what steuerbote/hgb/instance.py writes and steuerbote/hgb/upload.py guides, and
docs/architektur.md names both modules."""

from pathlib import Path
from unittest import TestCase

from steuerbote.hgb import upload
from steuerbote.hgb.disclosure import filing_fees
from steuerbote.hgb.instance import SLOTS, Code
from steuerbote.hgb.size import SizeClass
from steuerbote.hgb.tests import companies

DOCS = Path(__file__).resolve().parents[3] / "docs"
DOC = DOCS / "offenlegung.md"
GCD = "de-gcd:"


def section(heading: str) -> str:
	"""The text under a heading of the document, up to the next heading of the same or a higher level."""
	text = DOC.read_text(encoding="utf-8")
	level = heading.split(" ", 1)[0]
	start = text.index(f"\n{heading}\n")
	ends = [text.find(f"\n{'#' * depth} ", start + 1) for depth in range(1, len(level) + 1)]
	ends = [end for end in ends if end != -1]
	return text[start : min(ends) if ends else len(text)]


def rows(text: str, after: str = "") -> list[list[str]]:
	"""The cells of the rows of the first table in the text after a line, without its head."""
	if after:
		text = text[text.index(after) :]
	lines = text.splitlines()
	start = next(index for index, line in enumerate(lines) if line.startswith("|"))
	table = []
	for line in lines[start + 2 :]:
		if not line.startswith("|"):
			break
		table.append([cell.strip() for cell in line.strip().strip("|").split("|")])
	return table


def code(cell: str) -> str:
	return cell.strip("`")


class AngabenTest(TestCase):
	"""The places of the Angaben as SLOTS gives them, class by class and in the order of the catalogue."""

	def test_the_angaben_under_the_balance_sheet_of_a_kleinst(self):
		self.assertEqual(
			self.table("**Unter der Bilanz der Kleinstkapitalgesellschaft**"), self.slots(SizeClass.KLEINST)
		)

	def test_the_angaben_in_the_anhang_of_klein(self):
		self.assertEqual(self.table("**Im Anhang der kleinen Gesellschaft**"), self.slots(SizeClass.KLEIN))

	@staticmethod
	def table(title: str) -> list[tuple[str, str, str]]:
		return [tuple(code(cell) for cell in row) for row in rows(section("### Angaben"), title)]

	@staticmethod
	def slots(size_class: SizeClass) -> list[tuple[str, str, str]]:
		return [(slot.code, slot.text, slot.amount) for slot in SLOTS[size_class]]


class GcdTest(TestCase):
	"""Every field of the GCD an instance states, in the order the instances state them."""

	def setUp(self):
		self.fields = [code(row[0]) for row in rows(section("### Stammdaten (GCD)"))]

	@staticmethod
	def stated(offenlegung) -> list[str]:
		return [fact.concept.removeprefix(GCD) for fact in offenlegung.facts if fact.concept.startswith(GCD)]

	def test_names_every_field_an_instance_states(self):
		stated = {
			field for offenlegung in companies.instances().values() for field in self.stated(offenlegung)
		}
		self.assertEqual(set(self.fields), stated)
		self.assertEqual(len(self.fields), len(stated))

	def test_in_the_order_of_the_instances(self):
		for name, offenlegung in companies.instances().items():
			stated = self.stated(offenlegung)
			with self.subTest(name=name):
				self.assertEqual([field for field in self.fields if field in stated], stated)


class FindingsTest(TestCase):
	def test_names_every_code_of_the_file(self):
		self.assertEqual(
			[code(row[0]) for row in rows(section("### Befunde"))], [member.value for member in Code]
		)


class UploadTest(TestCase):
	"""The steps, the identification, the fees and the records of steuerbote/hgb/upload.py."""

	def test_the_steps_in_their_order(self):
		titles = [
			line.split("**")[1].removesuffix(":")
			for line in section("## Hochladen auf der Publikations-Plattform").splitlines()
			if line[:1].isdigit()
		]
		self.assertEqual(titles, [step.title for step in upload.STEPS])

	def test_the_test_platform_and_how_to_reach_it(self):
		self.assertIn(upload.TEST_PLATFORM_ADDRESS, section("## Hochladen auf der Publikations-Plattform"))

	def test_each_way_to_identify_with_its_fee(self):
		table = rows(section("### Identifizierung und Gebühren"))
		self.assertEqual(
			table,
			[
				[entry.label, f"{entry.fee:.2f} €".replace(".", ","), entry.reference]
				for entry in upload.IDENTIFICATION
			],
		)

	def test_the_fees_of_the_register(self):
		text = section("### Identifizierung und Gebühren")
		for size_class in (SizeClass.KLEINST, SizeClass.KLEIN):
			fees = filing_fees(size_class)
			with self.subTest(size_class=size_class):
				self.assertIn(f"{fees.filing:.2f} € ({fees.filing_reference})".replace(".", ",", 1), text)
				self.assertIn(f"{fees.yearly:.2f} €".replace(".", ","), text)
				self.assertIn(fees.yearly_reference, text)

	def test_what_to_record_afterwards(self):
		text = section("### Was danach festzuhalten ist")
		for record in upload.RECORDS:
			with self.subTest(field=record.field):
				self.assertIn(record.label, text)


class ArchitectureTest(TestCase):
	def test_names_both_modules_and_links_the_document(self):
		text = (DOCS / "architektur.md").read_text(encoding="utf-8")
		for name in ("`steuerbote/hgb/instance.py`", "`steuerbote/hgb/upload.py`", "(offenlegung.md)"):
			with self.subTest(name=name):
				self.assertIn(name, text)
