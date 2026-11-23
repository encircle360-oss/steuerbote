"""The XML of 2027 against UStVA-2027.xsd, elster11_UStVA_2027_extern.xsd and the examples of 2027 in the
documentation of the beta ERiC 45.1.5.0, from which the data of 2027 come provisionally (steuerbote/ustva/years.py).

The tests take the documentation from STEUERBOTE_ERIC_DOC_DIR, as test_schema.py does for 2026, and are skipped while
it holds no UStVA 2027, as the documentation 44.3.6.0 of the CI does not (eric_schema.ustva_year).
"""

from datetime import date
from decimal import Decimal
from unittest import TestCase

from lxml import etree

from steuerbote.dauerfrist import Context
from steuerbote.elster import ust1h_xml
from steuerbote.elster.envelope import envelope_of, to_envelope
from steuerbote.elster.tests import eric_schema
from steuerbote.elster.tests.examples import (
	OFFICIAL_EXAMPLE,
	anmeldung,
	antrag,
	balance,
	elements,
	filer,
	voranmeldung,
)
from steuerbote.elster.ustva_xml import (
	BEGRUENDUNG_LENGTH,
	DATENLIEFERANT,
	SCHEMAS,
	Filer,
	to_import_file,
	to_nutzdaten,
)
from steuerbote.ustva import Kind, Period, Rhythm, catalogue_for

YEAR = 2027
XS = "{http://www.w3.org/2001/XMLSchema}"
HERSTELLER_ID = "12345"
CREATED = date(2027, 2, 3)
JANUARY = Period.month(YEAR, 1)
# The DatenLieferant and Steuernummer of the examples of 2027 in the documentation of the beta ERiC 45.1.5.0, and the
# day they are made on.
EXAMPLE_FILER = {
	"steuernummer": "9198081508152",
	"name": "Alois Mustermann",
	"street": "Testgasse 13",
	"postal_code": "12345",
	"city": "Musterstadt",
	"phone": "12345678901",
	"email": "Mustermann@Geschaeft.de",
}
EXAMPLE_CREATED = date(2023, 1, 5)
# Kz 09 with the data of a Berater after the Hersteller-ID, which the schema of 2026 takes and that of 2027 no more.
KZ09_WITH_A_BERATER = "12345*Berater*Mandant*1*2*3"


def canonical(element: etree._Element) -> bytes:
	"""The element in Canonical XML 2.0, without comments and without the white space between elements."""
	return etree.tostring(element, method="c14n2", with_comments=False, strip_text=True)


def january(amounts: dict[str, Decimal] | None = None, **fields):
	return voranmeldung(amounts, period=JANUARY, **fields)


class Schema2027TestCase(TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.documentation = eric_schema.ustva_year(YEAR)
		cls.nutzdaten = eric_schema.nutzdaten_schema(YEAR)
		cls.envelope = eric_schema.envelope_schema(YEAR)

	def assert_valid(self, schema: etree.XMLSchema, document: bytes | str) -> None:
		data = document.encode("utf-8") if isinstance(document, str) else document
		if not schema.validate(etree.ElementTree(etree.fromstring(data))):
			self.fail(str(schema.error_log))

	def assert_invalid(self, schema: etree.XMLSchema, document: bytes | str) -> None:
		data = document.encode("utf-8") if isinstance(document, str) else document
		self.assertFalse(schema.validate(etree.ElementTree(etree.fromstring(data))))


class ImportFileTest(Schema2027TestCase):
	def test_january_follows_the_schema(self):
		self.assert_valid(self.nutzdaten, to_import_file(filer(), january(), CREATED))
		self.assert_valid(self.nutzdaten, to_nutzdaten(filer(), january(), CREATED, HERSTELLER_ID))

	def test_every_period_code_follows_the_schema(self):
		for rhythm, last in ((Rhythm.MONTHLY, 12), (Rhythm.QUARTERLY, 4)):
			for index in range(1, last + 1):
				period = Period(YEAR, rhythm, index)
				with self.subTest(code=period.code):
					document = to_import_file(filer(), voranmeldung(period=period), CREATED)
					self.assert_valid(self.nutzdaten, document)

	def test_every_element_follows_the_schema(self):
		catalogue = catalogue_for(YEAR)
		amounts = {number: Decimal("-1") for number, kennzahl in catalogue.items() if kennzahl.holds_amount}
		amounts.update({number: Decimal("1") for number in SCHEMAS[YEAR].unsigned})
		amounts["83"] = balance({number: amount for number, amount in amounts.items() if number != "83"})
		full = january(
			amounts,
			corrected=True,
			attachments=True,
			no_sepa_mandate=True,
			offset_requested=True,
			supplementary_code="2",
			begruendung="x" * BEGRUENDUNG_LENGTH,
			regelbesteuerung_from=date(YEAR, 12, 31),
		)
		longest = filer(
			wid_nr="DE123456789",
			**{attribute: "x" * field.length for attribute, field in DATENLIEFERANT.items()},
		)
		self.assert_valid(self.nutzdaten, to_import_file(longest, full, CREATED))
		self.assert_valid(self.nutzdaten, to_nutzdaten(longest, full, CREATED, HERSTELLER_ID))

	def test_kz09_takes_the_hersteller_id_alone(self):
		"""Jahresdokumentation_UStVA_2027.ods: Kz 09 of five digits, with the rule 110085046 on its length gone."""
		text = to_nutzdaten(filer(), january(), CREATED, HERSTELLER_ID)
		self.assertIn(f"<Kz09>{HERSTELLER_ID}</Kz09>", text)
		with_berater = text.replace(f"<Kz09>{HERSTELLER_ID}</Kz09>", f"<Kz09>{KZ09_WITH_A_BERATER}</Kz09>")
		self.assert_invalid(self.nutzdaten, with_berater)
		before = eric_schema.nutzdaten_schema(2026)
		self.assert_valid(before, with_berater.replace("/v2027", "/v2026").replace('"2027"', '"2026"'))

	def test_the_envelope_follows_the_schema(self):
		for testmerker in (True, False):
			with self.subTest(testmerker=testmerker):
				document = to_envelope(
					filer(phone="089 1234567", email="erika@example.org"),
					january(),
					CREATED,
					hersteller_id=HERSTELLER_ID,
					testmerker=testmerker,
					contact="Erika Beispiel",
				)
				self.assert_valid(self.envelope, document)


class StructureTest(Schema2027TestCase):
	"""The facts of the schema that ustva_xml.py writes down for 2027, compared with UStVA-2027.xsd itself."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls.xsd = etree.parse(str(eric_schema.nutzdaten_xsd(YEAR))).getroot()

	def sequence(self, prefix: str) -> list[tuple[str, str]]:
		(complex_type,) = (
			element
			for element in self.xsd.iterchildren(f"{XS}complexType")
			if element.get("name").startswith(prefix)
		)
		return [(element.get("name"), element.get("type")) for element in complex_type.iter(f"{XS}element")]

	def test_the_namespace_and_version_are_those_of_the_schema(self):
		self.assertEqual(self.xsd.get("targetNamespace"), SCHEMAS[YEAR].namespace)
		(version,) = self.xsd.iter(f"{XS}attribute")
		self.assertEqual((version.get("name"), version.get("fixed")), ("version", str(YEAR)))

	def test_the_order_is_that_of_the_schema(self):
		self.assertEqual(
			tuple(name for name, _ in self.sequence("Umsatzsteuervoranmeldung_")), SCHEMAS[YEAR].elements
		)

	def test_each_kennzahl_has_the_type_of_its_kind(self):
		catalogue = catalogue_for(YEAR)
		prefixes = {
			Kind.BASE: "Ganzzahl",
			Kind.TAX: "Dezimalzahl",
			Kind.FLAG: "Ja1",
			Kind.DATE: "DatumTTpMMpJJJJ",
			Kind.CODE: "Enum_",
		}
		for name, type_name in self.sequence("Umsatzsteuervoranmeldung_"):
			number = name.removeprefix("Kz")
			if number not in catalogue:
				continue
			with self.subTest(kennzahl=number):
				self.assertTrue(type_name.startswith(prefixes[catalogue[number].kind]), type_name)
				self.assertEqual("NichtNeg" in type_name, number in SCHEMAS[YEAR].unsigned, type_name)


class Ust1HTest(Schema2027TestCase):
	"""Form USt 1 H 2027 in both contexts of UStVA-2027.xsd."""

	def nutzdaten_of(self, filing, **fields) -> str:
		return ust1h_xml.to_nutzdaten(filer(**fields), filing, CREATED, HERSTELLER_ID)

	def test_both_contexts_follow_the_schema(self):
		for filing in (
			antrag(year=YEAR),
			anmeldung(year=YEAR),
			anmeldung(year=YEAR, sondervorauszahlung=Decimal("0")),
		):
			with self.subTest(context=filing.context, kz38=filing.sondervorauszahlung):
				self.assert_valid(self.nutzdaten, self.nutzdaten_of(filing))

	def test_every_element_follows_the_schema(self):
		longest = {
			"wid_nr": "DE123456789",
			**{attribute: "x" * field.length for attribute, field in DATENLIEFERANT.items()},
		}
		for filing in (
			anmeldung(
				year=YEAR,
				sondervorauszahlung=Decimal("9999999999999"),
				corrected=True,
				no_sepa_mandate=True,
				offset_requested=True,
				supplementary_code="4",
				begruendung="x" * BEGRUENDUNG_LENGTH,
			),
			antrag(year=YEAR, supplementary_code="1", begruendung="x" * BEGRUENDUNG_LENGTH),
		):
			with self.subTest(context=filing.context):
				self.assert_valid(self.nutzdaten, self.nutzdaten_of(filing, **longest))

	def test_kz09_takes_the_hersteller_id_alone_in_both_contexts(self):
		for filing in (antrag(year=YEAR), anmeldung(year=YEAR)):
			text = self.nutzdaten_of(filing)
			with self.subTest(context=filing.context):
				self.assertIn(f"<Kz09>{HERSTELLER_ID}</Kz09>", text)
				self.assert_invalid(
					self.nutzdaten,
					text.replace(f"<Kz09>{HERSTELLER_ID}</Kz09>", f"<Kz09>{KZ09_WITH_A_BERATER}</Kz09>"),
				)

	def test_the_envelope_follows_the_schema(self):
		for filing in (antrag(year=YEAR), anmeldung(year=YEAR)):
			for testmerker in (True, False):
				with self.subTest(context=filing.context, testmerker=testmerker):
					document = envelope_of(
						ust1h_xml.build(filer(), filing, CREATED, HERSTELLER_ID),
						filer(),
						hersteller_id=HERSTELLER_ID,
						testmerker=testmerker,
					)
					self.assert_valid(self.envelope, document)


class ExamplesTest(Schema2027TestCase):
	"""The examples of 2027 of the documentation: UStVA_2027.xml, UStVA_Df_2027.xml and UStVA_SoVZ_2027.xml."""

	def test_follow_the_schema(self):
		self.assert_valid(self.envelope, eric_schema.example(YEAR))
		for context in Context:
			with self.subTest(context=context):
				self.assert_valid(self.envelope, eric_schema.ust1h_example(YEAR, context.value))

	def test_writes_the_kennzahlen_of_the_example_of_the_voranmeldung(self):
		example = elements(eric_schema.example(YEAR))
		ours = elements(to_import_file(Filer(**EXAMPLE_FILER), january(OFFICIAL_EXAMPLE), EXAMPLE_CREATED))
		self.assertEqual([element for element in example if element[0] != "Kz09"], ours)

	def test_writes_the_examples_of_form_ust_1_h(self):
		"""Each example is the same document as ours with its data, once its comments, its Unternehmer, which
		Steuerbote does not write, and the Hersteller-ID 74931, which only illustrates the documentation, are gone."""
		filings = {
			Context.DAUERFRISTVERLAENGERUNG: antrag(year=YEAR),
			Context.UMSATZSTEUERSONDERVORAUSZAHLUNG: anmeldung(
				year=YEAR,
				sondervorauszahlung=Decimal("9999999999999"),
				corrected=True,
				no_sepa_mandate=True,
				offset_requested=True,
			),
		}
		for context, filing in filings.items():
			with self.subTest(context=context):
				(example,) = etree.fromstring(eric_schema.ust1h_example(YEAR, context.value)).iter(
					"{*}Anmeldungssteuern"
				)
				(unternehmer,) = example.iter("{*}Unternehmer")
				unternehmer.getparent().remove(unternehmer)
				(kz09,) = example.iter("{*}Kz09")
				self.assertEqual(kz09.text, "74931")
				kz09.text = HERSTELLER_ID
				ours = ust1h_xml.build(Filer(**EXAMPLE_FILER), filing, EXAMPLE_CREATED, HERSTELLER_ID)
				self.assertEqual(canonical(ours), canonical(example))
