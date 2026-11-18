"""The XML against the schemas of the ERiC documentation 44.3.6.0, see eric_schema.py.

The schemas check the shape of every element; the rules across elements, such as the pairs of a base and its
tax or Kz 83, are not in them and are tested in test_ustva_xml.py.
"""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from lxml import etree

from steuerbote.elster.charset import ALLOWED, EXCLUDED
from steuerbote.elster.envelope import to_envelope
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.tests.examples import (
	CREATED,
	EXAMPLE_MONTH,
	OFFICIAL_EXAMPLE,
	balance,
	children,
	elements,
	filer,
	voranmeldung,
	write,
)
from steuerbote.elster.ustva_xml import (
	BEGRUENDUNG_LENGTH,
	DATENLIEFERANT,
	SCHEMAS,
	to_import_file,
	to_nutzdaten,
)
from steuerbote.ustva import Kind, Period, Rhythm, catalogue_for

XS = "{http://www.w3.org/2001/XMLSchema}"


class SchemaTestCase(TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.nutzdaten = eric_schema.nutzdaten_schema(2026)
		cls.envelope = eric_schema.envelope_schema(2026)

	def assert_valid(self, schema: etree.XMLSchema, document: bytes | str) -> None:
		data = document.encode("utf-8") if isinstance(document, str) else document
		if not schema.validate(etree.ElementTree(etree.fromstring(data))):
			self.fail(str(schema.error_log))

	def assert_invalid(self, schema: etree.XMLSchema, document: bytes) -> None:
		self.assertFalse(schema.validate(etree.ElementTree(etree.fromstring(document))))


class ImportFileSchemaTest(SchemaTestCase):
	def test_the_example_month_follows_the_schema(self):
		self.assert_valid(self.nutzdaten, to_import_file(filer(), voranmeldung(), CREATED))

	def test_every_period_code_follows_the_schema(self):
		for rhythm, last in ((Rhythm.MONTHLY, 12), (Rhythm.QUARTERLY, 4)):
			for index in range(1, last + 1):
				period = Period(2026, rhythm, index)
				with self.subTest(code=period.code):
					self.assert_valid(
						self.nutzdaten, to_import_file(filer(), voranmeldung(period=period), CREATED)
					)

	def test_every_element_follows_the_schema(self):
		catalogue = catalogue_for(2026)
		amounts = {number: Decimal("-1") for number, kennzahl in catalogue.items() if kennzahl.holds_amount}
		amounts.update({number: Decimal("1") for number in SCHEMAS[2026].unsigned})
		amounts["83"] = balance({number: amount for number, amount in amounts.items() if number != "83"})
		full = voranmeldung(
			amounts,
			corrected=True,
			attachments=True,
			no_sepa_mandate=True,
			offset_requested=True,
			supplementary_code="3",
			begruendung="x" * BEGRUENDUNG_LENGTH,
			regelbesteuerung_from=date(2026, 12, 31),
		)
		longest = filer(
			wid_nr="DE123456789",
			**{attribute: "x" * field.length for attribute, field in DATENLIEFERANT.items()},
		)
		self.assert_valid(self.nutzdaten, to_import_file(longest, full, CREATED))
		self.assert_valid(self.nutzdaten, to_nutzdaten(longest, full, CREATED, "12345"))

	def test_the_largest_amounts_follow_the_schema(self):
		amounts = {
			"45": Decimal("-9999999999999"),
			"66": Decimal("99999999999.99"),
			"83": Decimal("-99999999999.99"),
		}
		self.assert_valid(self.nutzdaten, to_import_file(filer(), voranmeldung(amounts), CREATED))

	def test_every_character_elster_takes_follows_the_schema(self):
		characters = sorted(ALLOWED - {" "})
		for start in range(0, len(characters), 40):
			name = "".join(characters[start : start + 40])
			with self.subTest(name=name):
				self.assert_valid(self.nutzdaten, to_import_file(filer(name=name), voranmeldung(), CREATED))

	def test_the_characters_elster_refuses_fail_the_schema(self):
		text = to_import_file(filer(), voranmeldung(), CREATED).decode("iso-8859-15")
		for character in (
			*sorted(EXCLUDED),
			"\t",
			"\N{DOUBLE LOW-9 QUOTATION MARK}",
			"\N{LATIN SMALL LETTER L WITH STROKE}",
		):
			with self.subTest(character=f"U+{ord(character):04X}"):
				mutated = text.replace("<Name>Beispiel GmbH</Name>", f"<Name>Beispiel{character}GmbH</Name>")
				self.assert_invalid(self.nutzdaten, mutated.encode("iso-8859-15", errors="xmlcharrefreplace"))

	def test_the_schema_refuses_the_formats_the_rules_avoid(self):
		text = to_import_file(filer(), voranmeldung(), CREATED).decode("iso-8859-15")
		mutations = {
			"tax without cents": ("<Kz83>95.00</Kz83>", "<Kz83>95</Kz83>"),
			"tax with a comma": ("<Kz83>95.00</Kz83>", "<Kz83>95,00</Kz83>"),
			"tax with a plus sign": ("<Kz83>95.00</Kz83>", "<Kz83>+95.00</Kz83>"),
			"tax as negative zero": ("<Kz83>95.00</Kz83>", "<Kz83>-0.00</Kz83>"),
			"tax with a leading zero": ("<Kz83>95.00</Kz83>", "<Kz83>095.00</Kz83>"),
			"base with cents": ("<Kz81>1000</Kz81>", "<Kz81>1000.00</Kz81>"),
			"base as negative zero": ("<Kz81>1000</Kz81>", "<Kz81>-0</Kz81>"),
			"base with 14 digits": ("<Kz81>1000</Kz81>", "<Kz81>12345678901234</Kz81>"),
			"Kz 90 before Kz 93": (
				"<Kz83>95.00</Kz83>",
				"<Kz83>95.00</Kz83>\n<Kz90>10</Kz90>\n<Kz93>10</Kz93>",
			),
			"Kz 09 of four digits": ("<Kz21>", "<Kz09>1234</Kz09><Kz21>"),
			"W-IdNr with its suffix": ("<Kz21>", "<WIdNr>DE123456789-00001</WIdNr><Kz21>"),
		}
		for case, (old, new) in mutations.items():
			with self.subTest(case):
				self.assertIn(old, text)
				self.assert_invalid(self.nutzdaten, text.replace(old, new, 1).encode("iso-8859-15"))


class SchemaStructureTest(TestCase):
	"""The facts of the schema that ustva_xml.py writes down, compared with UStVA-2026.xsd itself."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.xsd = etree.parse(str(eric_schema.nutzdaten_xsd(2026))).getroot()

	def complex_type(self, prefix: str) -> list[tuple[str, str]]:
		"""Name and type of each element of the sequence of the complexType whose name starts with prefix."""
		(complex_type,) = (
			element
			for element in self.xsd.iterchildren(f"{XS}complexType")
			if element.get("name").startswith(prefix)
		)
		return [(element.get("name"), element.get("type")) for element in complex_type.iter(f"{XS}element")]

	def max_length(self, type_name: str) -> int:
		(simple_type,) = (
			element
			for element in self.xsd.iterchildren(f"{XS}simpleType")
			if element.get("name") == type_name
		)
		return int(simple_type.find(f"{XS}restriction/{XS}maxLength").get("value"))

	def test_the_namespace_and_version_are_those_of_the_schema(self):
		self.assertEqual(self.xsd.get("targetNamespace"), SCHEMAS[2026].namespace)
		(version,) = self.xsd.iter(f"{XS}attribute")
		self.assertEqual((version.get("name"), version.get("fixed")), ("version", "2026"))

	def test_the_order_is_that_of_the_schema(self):
		self.assertEqual(
			tuple(name for name, _ in self.complex_type("Umsatzsteuervoranmeldung_")), SCHEMAS[2026].elements
		)

	def test_each_kennzahl_has_the_type_of_its_kind(self):
		catalogue = catalogue_for(2026)
		prefixes = {
			Kind.BASE: "Ganzzahl",
			Kind.TAX: "Dezimalzahl",
			Kind.FLAG: "Ja1",
			Kind.DATE: "DatumTTpMMpJJJJ",
			Kind.CODE: "Enum_",
		}
		for name, type_name in self.complex_type("Umsatzsteuervoranmeldung_"):
			number = name.removeprefix("Kz")
			if number not in catalogue:
				continue
			with self.subTest(kennzahl=number):
				self.assertTrue(type_name.startswith(prefixes[catalogue[number].kind]), type_name)
				self.assertEqual("NichtNeg" in type_name, number in SCHEMAS[2026].unsigned, type_name)

	def test_the_lengths_of_the_texts_are_those_of_the_schema(self):
		types = dict(self.complex_type("DatenLieferant_"))
		self.assertEqual(
			{field.element: self.max_length(types[field.element]) for field in DATENLIEFERANT.values()},
			{field.element: field.length for field in DATENLIEFERANT.values()},
		)
		begruendung = dict(self.complex_type("Umsatzsteuervoranmeldung_"))["Kz500_Begruendung"]
		self.assertEqual(self.max_length(begruendung), BEGRUENDUNG_LENGTH)


class EnvelopeSchemaTest(SchemaTestCase):
	def test_the_envelope_follows_the_schema(self):
		for testmerker in (True, False):
			with self.subTest(testmerker=testmerker):
				document = to_envelope(
					filer(phone="089 1234567", email="erika@example.org"),
					voranmeldung(),
					CREATED,
					hersteller_id="12345",
					testmerker=testmerker,
					contact="Erika Beispiel",
				)
				self.assert_valid(self.envelope, document)

	def test_the_example_of_the_documentation_follows_the_schema(self):
		self.assert_valid(self.envelope, eric_schema.example(2026))

	def test_writes_the_kennzahlen_of_the_example_of_the_documentation(self):
		example = [element for element in elements(eric_schema.example(2026)) if element[0].startswith("Kz")]
		self.assertEqual(
			[element for element in example if element[0] != "Kz09"], list(write(OFFICIAL_EXAMPLE).items())
		)

	def test_the_example_month_has_the_shape_of_the_example_of_the_documentation(self):
		(example,) = etree.fromstring(eric_schema.example(2026)).iter("{*}Anmeldungssteuern")
		ours = etree.fromstring(to_import_file(filer(), voranmeldung(EXAMPLE_MONTH), CREATED))
		self.assertEqual((ours.tag, dict(ours.attrib)), (example.tag, dict(example.attrib)))
		self.assertEqual([name for name, _ in children(ours)], [name for name, _ in children(example)])
