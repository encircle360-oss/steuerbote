"""The Nutzdaten of the ZM against zm_000005.xsd, its envelope, its example and its Jahresdokumentation.

The files come from the ERiC documentation 44.3.6.0, see eric_schema.py. The schema checks the shape of each
element; the rules across elements and those that need the day of the transmission are tested in test_zm_xml.py.
"""

import re
from datetime import date
from decimal import Decimal
from unittest import TestCase

from lxml import etree

from steuerbote.elster import zm_xml
from steuerbote.elster.charset import ALLOWED
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.tests.zm_examples import AUSTRIA, CREATED, LINES, line, nutzdaten, unternehmer, zm
from steuerbote.elster.ustva_xml import XmlError
from steuerbote.elster.zm_xml import NAMESPACE, Meldeart, Unternehmer, Zm, to_nutzdaten
from steuerbote.vatid.ustid import GERMAN
from steuerbote.zm.lines import Art, Meldezeile
from steuerbote.zm.period import ReportingPeriod

XS = "{http://www.w3.org/2001/XMLSchema}"
Z = f"{{{NAMESPACE}}}"
TESTMERKER = "700000004"


def envelope(nutzdaten_xml: str, testmerker: bool) -> bytes:
	"""A whole ElsterXML delivery as EricCreateTH completes it, with the header the transmission needs for ZMDO."""

	def append(
		parent: etree._Element, name: str, value: str | None = None, **attributes: str
	) -> etree._Element:
		child = etree.SubElement(parent, Z + name, attributes)
		child.text = value
		return child

	root = etree.Element(Z + "Elster", nsmap={None: NAMESPACE})
	header = append(root, "TransferHeader", version="11")
	append(header, "Verfahren", zm_xml.VERFAHREN)
	append(header, "DatenArt", zm_xml.DATENART)
	append(header, "Vorgang", zm_xml.VORGANG)
	if testmerker:
		append(header, "Testmerker", TESTMERKER)
	append(header, "HerstellerID", "12345")
	append(header, "DatenLieferant", "Beispiel GmbH")
	datei = append(header, "Datei")
	append(datei, "Verschluesselung", "CMSEncryptedData")
	append(datei, "Kompression", "GZIP")
	block = append(append(root, "DatenTeil"), "Nutzdatenblock")
	nutzdaten_header = append(block, "NutzdatenHeader", version="11")
	append(nutzdaten_header, "NutzdatenTicket", "1")
	append(nutzdaten_header, "Empfaenger", zm_xml.EMPFAENGER, id=zm_xml.EMPFAENGER_ID)
	hersteller = append(nutzdaten_header, "Hersteller")
	append(hersteller, "ProduktName", "steuerbote")
	append(hersteller, "ProduktVersion", "0.2.0")
	append(block, "Nutzdaten").append(etree.fromstring(nutzdaten_xml.encode("utf-8")))
	return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def statement_of_the_example(example: bytes) -> tuple[Unternehmer, Zm]:
	"""The Unternehmer and the Zm of the documentation's example, from its own values."""
	(zm_element,) = etree.fromstring(example).iter(Z + "zm")

	def value(path: str) -> str | None:
		return zm_element.findtext("/".join(Z + name for name in path.split("/")))

	anschrift = {
		attribute: value(f"unternehmer/anschrift/{field.element}")
		for attribute, field in zm_xml.ANSCHRIFT.items()
	}
	filer = Unternehmer(ust_idnr=value("unternehmer/knri"), **anschrift)
	zeilen = zm_element.find(f"{Z}unternehmer/{Z}zm-zeilen")
	lines = tuple(
		Meldezeile(
			zeile.findtext(Z + "knre"), Art(zeile.get("umsatzart")), Decimal(zeile.findtext(Z + "betrag"))
		)
		for zeile in zeilen.iter(Z + "zeile")
	)
	period = ReportingPeriod.from_quart(
		int(value("unternehmer/zm-zeilen/mzr/jahr")), int(value("unternehmer/zm-zeilen/mzr/quart"))
	)
	assert zeilen.get("meldeart") == Meldeart.ERSTMELDUNG.value
	statement = Zm(
		period,
		lines,
		anzeige=value("unternehmer/zm-zeilen/anzeige") == "true",
		widerruf=value("unternehmer/zm-zeilen/widerruf") == "true",
	)
	return filer, statement


class SchemaTestCase(TestCase):
	def assert_valid(self, schema: etree.XMLSchema, document: bytes | str) -> None:
		data = document.encode("utf-8") if isinstance(document, str) else document
		if not schema.validate(etree.ElementTree(etree.fromstring(data))):
			self.fail(str(schema.error_log))


class NutzdatenSchemaTest(SchemaTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.schema = eric_schema.zm_schema()

	def test_a_minimal_statement_follows_the_schema(self):
		filer = Unternehmer(ust_idnr="DE123456789", name="B", street="S", postal_code="01001", city="O")
		self.assert_valid(self.schema, to_nutzdaten(filer, zm([line(AUSTRIA, Art.L, "1")]), CREATED))

	def test_the_statement_of_october_follows_the_schema(self):
		self.assert_valid(self.schema, nutzdaten())

	def test_a_full_statement_follows_the_schema(self):
		"""Every element at its longest, an own Teilnehmernummer, 5,000 lines of the largest sums with a cancelled
		one in a Berichtigung, and the Widerruf of the Anzeige in the third month of a quarter."""
		filer = unternehmer(
			name="x" * 100,
			address_suffix="x" * 40,
			street="x" * 30,
			house_number="x" * 10,
			house_number_suffix="x" * 10,
			postal_code="99999",
			city="x" * 30,
			phone="+49 (0) 89/123-4567",
			teilnehmernummer="99999999",
		)
		current = tuple(
			line(f"ATU{number:08d}", [*Art][number % 3], f"{'-' if number % 2 else ''}99999999999")
			for number in range(4999)
		)
		statement = Zm(
			ReportingPeriod.month(2026, 9),
			current,
			filed={("FR12345678901", Art.S): Decimal("1")},
			widerruf=True,
		)
		self.assertEqual((len(statement.reported), statement.reported[0].amount), (5000, Decimal("0")))
		self.assert_valid(self.schema, to_nutzdaten(filer, statement, CREATED))

	def test_a_foreign_address_follows_the_schema(self):
		filer = unternehmer(country="XU", postal_code="SW1A 1AA", phone=None)
		self.assert_valid(self.schema, to_nutzdaten(filer, zm(), CREATED))
		self.assert_valid(
			self.schema, to_nutzdaten(unternehmer(country="AT", postal_code=None), zm(), CREATED)
		)

	def test_every_meldezeitraum_follows_the_schema(self):
		periods = [
			*(ReportingPeriod.month(2026, month) for month in range(1, 13)),
			*(ReportingPeriod.two_months(2026, quarter) for quarter in range(1, 5)),
			*(ReportingPeriod.quarter(2026, quarter) for quarter in range(1, 5)),
			ReportingPeriod.calendar_year(2026),
		]
		for period in periods:
			with self.subTest(period=period.label):
				anzeige = period.first_month == period.last_month
				statement = zm(period=period, anzeige=anzeige)
				self.assert_valid(self.schema, to_nutzdaten(unternehmer(), statement, date(2027, 1, 1)))

	def test_the_schema_refuses_what_the_rules_avoid(self):
		text = nutzdaten()
		mutations = {
			"another version": ('version="000005"', 'version="000004"'),
			"another Paginierbuchstabe": ("<zulnr1>N</zulnr1>", "<zulnr1>X</zulnr1>"),
			"a Teilnehmernummer below 0300000": ("<zulnr2>1111111</zulnr2>", "<zulnr2>0299999</zulnr2>"),
			"a foreign knri": ("<knri>DE123456789</knri>", "<knri>ATU12345678</knri>"),
			"an empty name": ("<name>Beispiel GmbH</name>", "<name></name>"),
			"a name of 101 characters": ("<name>Beispiel GmbH</name>", f"<name>{'x' * 101}</name>"),
			"a state of three letters": ("<staat>DE</staat>", "<staat>DEU</staat>"),
			"a phone with a hash": ("<staat>DE</staat>", "<staat>DE</staat><telefon>089#1</telefon>"),
			"no staat": ("<staat>DE</staat>", ""),
			"another currency": ('waehrung="1"', 'waehrung="2"'),
			"another meldeart": ('meldeart="10"', 'meldeart="12"'),
			"anzeige as 1": ("<anzeige>false</anzeige>", "<anzeige>1</anzeige>"),
			"no widerruf": ("<widerruf>false</widerruf>", ""),
			"quart 33": ("<quart>30</quart>", "<quart>33</quart>"),
			"jahr 1899": ("<jahr>2026</jahr>", "<jahr>1899</jahr>"),
			"another Art": ('umsatzart="S"', 'umsatzart="X"'),
			"a sum with cents": ("<betrag>3500</betrag>", "<betrag>3500.00</betrag>"),
			"a sum of 12 digits": ("<betrag>3500</betrag>", "<betrag>100000000000</betrag>"),
			"a knre without country code": ("<knre>ATU12345678</knre>", "<knre>12345678</knre>"),
		}
		for case, (old, new) in mutations.items():
			with self.subTest(case):
				self.assertIn(old, text)
				document = etree.ElementTree(etree.fromstring(text.replace(old, new, 1).encode("utf-8")))
				self.assertFalse(self.schema.validate(document))


class EnvelopeSchemaTest(SchemaTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.schema = eric_schema.zm_envelope_schema()

	def test_the_example_of_the_documentation_follows_the_schema(self):
		self.assert_valid(self.schema, eric_schema.zm_example())

	def test_the_nutzdaten_follow_the_schema_in_the_envelope_of_zmdo(self):
		for testmerker in (True, False):
			with self.subTest(testmerker=testmerker):
				self.assert_valid(self.schema, envelope(nutzdaten(), testmerker))

	def test_the_example_is_sent_as_zm_xml_names_it(self):
		root = etree.fromstring(eric_schema.zm_example())
		header = root.find(Z + "TransferHeader")
		self.assertEqual(
			[header.findtext(Z + name) for name in ("Verfahren", "DatenArt", "Vorgang")],
			[zm_xml.VERFAHREN, zm_xml.DATENART, zm_xml.VORGANG],
		)
		(recipient,) = root.iter(Z + "Empfaenger")
		self.assertEqual((recipient.get("id"), recipient.text), (zm_xml.EMPFAENGER_ID, zm_xml.EMPFAENGER))

	def test_writes_the_example_of_the_documentation_byte_for_byte(self):
		"""Every field of the example is one zm_xml.py writes, so the Nutzdaten of its own values are its element zm
		byte for byte, without the indentation of the envelope and with a line feed for each CR LF."""
		example = eric_schema.zm_example()
		lines = example.decode("utf-8").replace("\r\n", "\n").split("\n")
		start = next(index for index, text in enumerate(lines) if text.lstrip().startswith("<zm "))
		end = next(index for index, text in enumerate(lines) if text.strip() == "</zm>")
		indent = lines[start][: lines[start].index("<")]
		self.assertTrue(all(text.startswith(indent) for text in lines[start : end + 1]))
		expected = "".join(text.removeprefix(indent) + "\n" for text in lines[start : end + 1])
		filer, statement = statement_of_the_example(example)
		self.assertEqual(to_nutzdaten(filer, statement, CREATED).encode("utf-8"), expected.encode("utf-8"))


class SchemaStructureTest(TestCase):
	"""The facts of zm_000005.xsd that zm_xml.py writes down, compared with the schema itself."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.xsd = etree.parse(str(eric_schema.zm_xsd())).getroot()

	def simple_type(self, name: str) -> etree._Element:
		(element,) = (element for element in self.xsd.iter(f"{XS}simpleType") if element.get("name") == name)
		return element

	def facets(self, name: str, facet: str) -> list[str]:
		return [element.get("value") for element in self.simple_type(name).iter(f"{XS}{facet}")]

	def test_the_version_is_the_constant_of_the_schema(self):
		(version,) = (
			attribute for attribute in self.xsd.iter(f"{XS}attribute") if attribute.get("name") == "version"
		)
		self.assertEqual(
			[element.get("value") for element in version.iter(f"{XS}enumeration")], [zm_xml.VERSION]
		)

	def test_the_namespace_is_that_of_the_envelope(self):
		envelope_xsd = eric_schema.zm_xsd().with_name("elster11_Zm_000005_extern.xsd")
		self.assertEqual(etree.parse(str(envelope_xsd)).getroot().get("targetNamespace"), NAMESPACE)

	def test_the_address_has_the_order_lengths_and_required_parts_of_the_schema(self):
		(anschrift,) = (
			element
			for element in self.xsd.iter(f"{XS}complexType")
			if element.get("name") == "anschrift_Type"
		)
		elements = [
			(
				element.get("name"),
				int(element.find(f".//{XS}maxLength").get("value")),
				element.get("minOccurs") != "0",
			)
			for element in anschrift.iter(f"{XS}element")
		]
		self.assertEqual(
			elements,
			[(field.element, field.length, field.required) for field in zm_xml.ANSCHRIFT.values()],
		)

	def test_the_codes_are_those_of_the_schema(self):
		self.assertEqual(self.facets("meldeart_Type", "enumeration"), sorted(item.value for item in Meldeart))
		self.assertIn(zm_xml.EURO, self.facets("waehrung_Type", "enumeration"))
		self.assertEqual(set(self.facets("umsatzart_Type", "enumeration")), {art.value for art in Art})
		self.assertIn(zm_xml.ZULNR1, self.facets("zulassNr1_Type", "enumeration"))
		self.assertEqual(self.facets("boolean_Type", "enumeration"), ["true", "false"])
		self.assertEqual(self.facets("knri_Type", "pattern"), [GERMAN.pattern])

	def test_the_sums_take_eleven_digits_and_a_sign(self):
		limit = 10**zm_xml.AMOUNT_DIGITS - 1
		self.assertEqual(
			(self.facets("betrag_Type", "minInclusive"), self.facets("betrag_Type", "maxInclusive")),
			([str(-limit)], [str(limit)]),
		)

	def test_the_teilnehmernummer_has_the_range_of_the_schema(self):
		self.assertEqual(
			[
				int(value)
				for value in (
					*self.facets("zulassNr2_Type", "minInclusive"),
					*self.facets("zulassNr2_Type", "maxInclusive"),
				)
			],
			[zm_xml.TEILNEHMERNUMMER_MIN, 99999999],
		)

	def test_the_phone_takes_the_characters_of_the_schema(self):
		(telefon,) = (
			element for element in self.xsd.iter(f"{XS}element") if element.get("name") == "telefon"
		)
		(pattern,) = (element.get("value") for element in telefon.iter(f"{XS}pattern"))
		for character in sorted(ALLOWED):
			with self.subTest(character=character):
				self.assertEqual(
					re.fullmatch(pattern, character) is not None,
					zm_xml.PHONE.fullmatch(character) is not None,
				)


class JahresdokumentationTest(TestCase):
	"""The facts of Jahresdokumentation_ZMDO_2.ods and Datenartversionmatrix.ods that zm_xml.py writes down."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.fields = {row["Name"]: row for row in eric_schema.zm_fields()}

	def pattern(self, name: str) -> str:
		return self.fields[name]["Format als regulärer Ausdruck"]

	def test_takes_at_most_5000_lines(self):
		for name in ("umsatzart", "knre_UstIdNr_Erwerber", "betrag"):
			with self.subTest(name=name):
				self.assertEqual(self.fields[name]["max. Zeilen"], str(zm_xml.MAX_LINES))

	def test_the_countries_are_those_of_the_field_staat(self):
		self.assertEqual(set(re.findall(r"\\Q([A-Z]{2})\\E", self.pattern("staat"))), zm_xml.COUNTRIES)

	def test_the_teilnehmernummer_of_eric(self):
		self.assertIn(f"„{zm_xml.ZULNR1}“", self.fields["zulnr1_Teilnehmernummer"]["Zusatz-Informationen"])
		self.assertIn(f"„{zm_xml.ZULNR2}“", self.fields["zulnr2_Teilnehmernummer"]["Zusatz-Informationen"])
		pattern = self.pattern("zulnr2_Teilnehmernummer")
		for number in ("0300000", "1111111", "99999999", "0299999", "0000000", "123456", "123456789"):
			with self.subTest(number=number):
				documented = re.fullmatch(pattern, number) is not None
				documented = documented and int(number) >= zm_xml.TEILNEHMERNUMMER_MIN
				self.assertEqual(self.accepts(teilnehmernummer=number), documented)

	def test_the_euro(self):
		self.assertEqual(self.pattern("waehrung"), rf"\Q{zm_xml.EURO}\E")

	def test_the_sums_as_written_follow_the_format_of_betrag(self):
		pattern = self.pattern("betrag")
		for amount in ("-99999999999", "-1", "1", "1000", "99999999999"):
			with self.subTest(amount=amount):
				(written,) = re.findall(
					r"<betrag>(.*)</betrag>", nutzdaten(zm([line(AUSTRIA, Art.L, amount)]))
				)
				self.assertRegex(written, pattern)
		cancelled = Zm(ReportingPeriod.month(2026, 10), LINES, filed={("FR98765432101", Art.L): Decimal("5")})
		self.assertRegex(re.findall(r"<betrag>(.*)</betrag>", nutzdaten(cancelled))[0], pattern)

	def test_the_postal_code_and_the_phone_take_the_characters_of_their_fields(self):
		for character in sorted(ALLOWED - {" "}):
			with self.subTest(character=character):
				self.assertEqual(
					self.accepts(country="AT", postal_code=f"1{character}"),
					re.fullmatch(self.pattern("plz"), f"1{character}") is not None,
				)
				self.assertEqual(
					self.accepts(phone=f"1{character}"),
					re.fullmatch(self.pattern("telefon"), f"1{character}") is not None,
				)

	def test_the_recipient_is_bf(self):
		self.assertEqual(self.pattern("EmpfaengerTyp"), rf"\Q{zm_xml.EMPFAENGER_ID}\E")
		self.assertIn(rf"\Q{zm_xml.EMPFAENGER}\E", self.pattern("EmpfaengerName").split("|"))

	def test_zmdo_is_elster_extern_with_the_plugin_check_zmdo(self):
		(row,) = (row for row in eric_schema.datenart_versions() if row["Datenart(en)"] == zm_xml.DATENART)
		self.assertEqual(
			(
				row["Verfahren"],
				row["Jahr / Version"],
				row["datenartVersion-Parameter"],
				row["Plugin-Bibliothek"],
			),
			(zm_xml.VERFAHREN, "", zm_xml.DATENART_VERSION, zm_xml.PLUGIN),
		)

	def accepts(self, **fields: object) -> bool:
		try:
			unternehmer(**fields)
		except XmlError:
			return False
		return True
