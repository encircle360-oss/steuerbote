from dataclasses import replace
from unittest import TestCase
from xml.etree import ElementTree

from lxml import etree

from steuerbote.elster import ust1h_xml, ustva_xml
from steuerbote.elster.tests import eric_schema, examples, zm_examples
from steuerbote.eric.datenart import ZMDO, Datenart, bilanz, gewst, kst, ust, ustva
from steuerbote.eric.header import (
	ILLUSTRATION_HERSTELLER_ID,
	EnvelopeHeader,
	datenteil,
	nutzdaten_datenlieferant,
	problems,
)
from steuerbote.eric.result import ERROR, TESTMERKER, Operation

NUTZDATEN = (
	'<Anmeldungssteuern xmlns="http://finkonsens.de/elster/elsteranmeldung/ustva/v2026" version="2026">'
	"<Steuerfall><Umsatzsteuervoranmeldung><Jahr>2026</Jahr><Zeitraum>10</Zeitraum>"
	"<Kz83>95.00</Kz83></Umsatzsteuervoranmeldung></Steuerfall></Anmeldungssteuern>"
)

HEADER = EnvelopeHeader(
	hersteller_id="12345",
	datenlieferant="Beispiel GmbH; Erika Beispiel; 089 1234567",
	produkt_name="Steuerbote",
	produkt_version="0.1.0",
	empfaenger="9198",
	datenart_version="UStVA_2026",
	testmerker=None,
	nutzdaten_ticket="1",
)
# The Zusammenfassende Meldung goes to the Länderkürzel BF (ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 8-28).
ZM_HEADER = replace(HEADER, empfaenger="BF", datenart_version="ZMDO")
# The ten parts of the DatenLieferant of an E-Bilanz (Kap. 9.7.1), invented.
ERSTELLER = (
	"Beispiel GmbH; Hauptstraße; 1; a; Hinterhaus; 80331; München; Deutschland; 089 1234567; info@example.org"
)
BILANZ_HEADER = replace(HEADER, datenart_version="Bilanz_6.9", nutzdaten_datenlieferant=ERSTELLER)


def delivery(datenteil_xml: str, kind: Datenart, testmerker: bool) -> bytes:
	"""The whole delivery as EricCreateTH completes the DatenTeil: the TransferHeader of the Datenart before it and
	the namespace of ElsterXML 11 on <Elster> alone (API-Referenz, EricCreateTH)."""
	test = f"<Testmerker>{TESTMERKER}</Testmerker>" if testmerker else ""
	return (
		'<Elster xmlns="http://www.elster.de/elsterxml/schema/v11"><TransferHeader version="11">'
		f"<Verfahren>{kind.verfahren}</Verfahren><DatenArt>{kind.name}</DatenArt><Vorgang>{kind.vorgang}</Vorgang>"
		f"{test}<HerstellerID>12345</HerstellerID><DatenLieferant>Beispiel GmbH</DatenLieferant>"
		"<Datei><Verschluesselung>CMSEncryptedData</Verschluesselung><Kompression>GZIP</Kompression></Datei>"
		f"</TransferHeader>{datenteil_xml}</Elster>"
	).encode()


class DatenteilTest(TestCase):
	def test_heads_the_nutzdaten_with_the_nutzdaten_header(self):
		root = ElementTree.fromstring(datenteil(NUTZDATEN, HEADER))
		self.assertEqual(root.tag, "DatenTeil")
		self.assertEqual(root.attrib, {})
		header = root.find("Nutzdatenblock/NutzdatenHeader")
		self.assertEqual(header.attrib, {"version": "11"})
		self.assertEqual(header.findtext("NutzdatenTicket"), "1")
		self.assertEqual(header.find("Empfaenger").attrib, {"id": "F"})
		self.assertEqual(header.findtext("Empfaenger"), "9198")
		self.assertEqual(header.findtext("Hersteller/ProduktName"), "Steuerbote")
		self.assertEqual(header.findtext("Hersteller/ProduktVersion"), "0.1.0")
		nutzdaten = root.find("Nutzdatenblock/Nutzdaten")
		self.assertEqual(
			[child.tag for child in nutzdaten],
			["{http://finkonsens.de/elster/elsteranmeldung/ustva/v2026}Anmeldungssteuern"],
		)

	def test_keeps_the_nutzdaten_as_they_are(self):
		self.assertIn(f"<Nutzdaten>{NUTZDATEN}</Nutzdaten>", datenteil(NUTZDATEN, HEADER))

	def test_drops_the_declaration_and_byte_order_mark_of_the_nutzdaten(self):
		for prefix in (
			'<?xml version="1.0" encoding="ISO-8859-15" standalone="no"?>\n',
			"\ufeff<?xml version='1.0'?>",
			"\ufeff",
			"\n  ",
		):
			with self.subTest(prefix=prefix):
				self.assertIn(f"<Nutzdaten>{NUTZDATEN}</Nutzdaten>", datenteil(prefix + NUTZDATEN, HEADER))

	def test_sends_the_zm_to_the_laenderkuerzel_bf(self):
		"""ERiC-Entwicklerhandbuch 44.3.6.0, Tabelle 8-28: <Empfaenger> with the attribute id "L"."""
		root = ElementTree.fromstring(datenteil(zm_examples.nutzdaten(), ZM_HEADER))
		header = root.find("Nutzdatenblock/NutzdatenHeader")
		self.assertEqual(
			(header.find("Empfaenger").attrib, header.findtext("Empfaenger")), ({"id": "L"}, "BF")
		)
		nutzdaten = root.find("Nutzdatenblock/Nutzdaten")
		self.assertEqual(
			[child.tag for child in nutzdaten], ["{http://www.elster.de/elsterxml/schema/v11}zm"]
		)

	def test_writes_the_datenlieferant_of_the_nutzdaten_header_after_the_hersteller(self):
		"""ndh000011.xsd: DatenLieferant follows Hersteller; the E-Bilanz names it there (Kap. 9.7.1)."""
		header = ElementTree.fromstring(datenteil("<EBilanz/>", BILANZ_HEADER)).find(
			"Nutzdatenblock/NutzdatenHeader"
		)
		self.assertEqual(
			[child.tag for child in header], ["NutzdatenTicket", "Empfaenger", "Hersteller", "DatenLieferant"]
		)
		self.assertEqual(header.findtext("DatenLieferant"), ERSTELLER)
		escaped = datenteil("<EBilanz/>", replace(BILANZ_HEADER, nutzdaten_datenlieferant="A & B <C>"))
		self.assertIn("<DatenLieferant>A &amp; B &lt;C&gt;</DatenLieferant>", escaped)

	def test_a_header_without_it_writes_none(self):
		header = ElementTree.fromstring(datenteil(NUTZDATEN, HEADER)).find("Nutzdatenblock/NutzdatenHeader")
		self.assertEqual([child.tag for child in header], ["NutzdatenTicket", "Empfaenger", "Hersteller"])

	def test_escapes_the_header_values(self):
		text = datenteil(NUTZDATEN, replace(HEADER, produkt_name="A & B <C>"))
		self.assertIn("<ProduktName>A &amp; B &lt;C&gt;</ProduktName>", text)
		self.assertEqual(ElementTree.fromstring(text).findtext(".//ProduktName"), "A & B <C>")


class ProblemsTest(TestCase):
	def fields(self, header: EnvelopeHeader, operation: Operation = Operation.VALIDATE, **options) -> list:
		found = problems(header, operation, **options)
		self.assertTrue(all(message.severity == ERROR and message.code == "SB-HEADER" for message in found))
		return [message.field for message in found]

	def test_accepts_a_complete_header(self):
		self.assertEqual(self.fields(HEADER, own_hersteller_id="12345"), [])
		self.assertEqual(self.fields(HEADER, Operation.SEND, own_hersteller_id="12345"), [])

	def test_a_test_send_needs_the_testmerker_and_a_send_none(self):
		test = replace(HEADER, testmerker=TESTMERKER)
		self.assertEqual(self.fields(test, Operation.TEST_SEND), [])
		self.assertEqual(self.fields(HEADER, Operation.TEST_SEND), ["Testmerker"])
		self.assertEqual(
			self.fields(replace(HEADER, testmerker="700000001"), Operation.TEST_SEND), ["Testmerker"]
		)
		self.assertEqual(self.fields(test, Operation.SEND), ["Testmerker"])
		self.assertEqual(self.fields(test, Operation.VALIDATE), [])

	def test_needs_the_own_hersteller_id_when_one_is_set_up(self):
		for own in ("", "1234", "123456", "1234a", ILLUSTRATION_HERSTELLER_ID):
			with self.subTest(own=own):
				header = replace(HEADER, hersteller_id=own)
				self.assertEqual(self.fields(header, own_hersteller_id=own), ["HerstellerID"])
				self.assertEqual(self.fields(header), [])

	def test_the_header_names_the_hersteller_id_that_is_set_up(self):
		self.assertEqual(self.fields(HEADER, own_hersteller_id="54321"), ["HerstellerID"])
		self.assertEqual(self.fields(replace(HEADER, hersteller_id="00000")), [])

	def test_names_each_field_out_of_shape(self):
		cases = {
			"Empfaenger": {"empfaenger": "919"},
			"NutzdatenTicket": {"nutzdaten_ticket": "x" * 33},
			"ProduktName": {"produkt_name": "ELSTER-Helfer"},
			"ProduktVersion": {"produkt_version": ""},
			"DatenLieferant": {"datenlieferant": " "},
			"datenartVersion": {"datenart_version": "UStVA_26"},
		}
		for field, change in cases.items():
			with self.subTest(field=field):
				self.assertEqual(self.fields(replace(HEADER, **change)), [field])

	def test_the_recipient_is_the_one_of_the_datenart(self):
		"""The UStVA goes to a Bundesfinanzamtsnummer (Tabelle 8-8), ZMDO to BF (Tabelle 8-28)."""
		self.assertEqual(self.fields(ZM_HEADER, Operation.SEND, own_hersteller_id="12345"), [])
		self.assertEqual(self.fields(replace(ZM_HEADER, empfaenger="9198")), ["Empfaenger"])
		self.assertEqual(self.fields(replace(HEADER, empfaenger="BF")), ["Empfaenger"])
		(refused,) = problems(replace(ZM_HEADER, empfaenger="9198"), Operation.VALIDATE)
		self.assertIn("BF", refused.text)

	def test_an_unknown_datenart_version_leaves_the_recipient_unchecked(self):
		self.assertEqual(
			self.fields(replace(HEADER, datenart_version="ESt_2026", empfaenger="x")), ["datenartVersion"]
		)

	def test_limits_follow_the_schema(self):
		self.assertEqual(self.fields(replace(HEADER, nutzdaten_ticket="x" * 32)), [])
		self.assertEqual(self.fields(replace(HEADER, nutzdaten_ticket="")), ["NutzdatenTicket"])
		self.assertEqual(self.fields(replace(HEADER, produkt_name="x" * 50)), [])
		self.assertEqual(self.fields(replace(HEADER, produkt_name="x" * 51)), ["ProduktName"])
		self.assertEqual(self.fields(replace(HEADER, produkt_version="1" * 51)), ["ProduktVersion"])
		self.assertEqual(self.fields(replace(HEADER, datenlieferant="x" * 256)), [])
		self.assertEqual(self.fields(replace(HEADER, datenlieferant="x" * 257)), ["DatenLieferant"])

	def test_the_bilanz_needs_the_datenlieferant_of_its_nutzdaten_header_in_ten_parts(self):
		"""Kap. 9.7.1: „Name des Erstellers; Strasse; Hausnummer; Hausnummerzusatz; Adresszusatz; PLZ; Ort; Land;
		Telefon; E-Mail-Adresse“, at most 256 characters."""
		field = "NutzdatenHeader/DatenLieferant"
		self.assertEqual(self.fields(BILANZ_HEADER, Operation.SEND, own_hersteller_id="12345"), [])
		nine = ERSTELLER.rpartition(";")[0]
		eleven = ERSTELLER + "; Erika Beispiel"
		for case, datenlieferant in {
			"none": None,
			"empty": "",
			"nine parts": nine,
			"eleven parts": eleven,
			"no name": "; Hauptstraße; 1; ; ; 80331; München; Deutschland; ;",
			"a blank at the end": "Beispiel GmbH; Hauptstraße; 1; ; ; 80331; München; Deutschland; ; ",
			"too long": ERSTELLER + "x" * (257 - len(ERSTELLER)),
		}.items():
			with self.subTest(case):
				header = replace(BILANZ_HEADER, nutzdaten_datenlieferant=datenlieferant)
				self.assertEqual(self.fields(header), [field])
		longest = ERSTELLER + "x" * (256 - len(ERSTELLER))
		self.assertEqual(self.fields(replace(BILANZ_HEADER, nutzdaten_datenlieferant=longest)), [])
		(refused,) = problems(replace(BILANZ_HEADER, nutzdaten_datenlieferant=nine), Operation.VALIDATE)
		self.assertIn("zehn", refused.text)

	def test_the_datenlieferant_of_the_nutzdaten_header_ends_without_a_blank(self):
		"""ERiC 44.3.6.0 refuses a value of the NutzdatenHeader that ends with a blank, „nachfolgendesBlank“
		(validation of Bilanz_6.9 with an E-Bilanz whose company names no e-mail address)."""
		(refused,) = problems(
			replace(BILANZ_HEADER, nutzdaten_datenlieferant=ERSTELLER.rpartition(";")[0] + "; "),
			Operation.VALIDATE,
		)
		self.assertEqual(refused.field, "NutzdatenHeader/DatenLieferant")
		self.assertIn("Leerzeichen", refused.text)

	def test_another_datenart_may_name_a_datenlieferant_of_at_most_256_characters(self):
		"""DatenLieferantInternSType of headerbasis_datentypen.xsd."""
		self.assertEqual(self.fields(replace(HEADER, nutzdaten_datenlieferant="Beispiel GmbH")), [])
		self.assertEqual(
			self.fields(replace(HEADER, nutzdaten_datenlieferant="x" * 257)),
			["NutzdatenHeader/DatenLieferant"],
		)

	def test_the_product_name_must_not_contain_elster_in_any_case(self):
		self.assertEqual(self.fields(replace(HEADER, produkt_name="Mein Elster")), ["ProduktName"])


class NutzdatenDatenlieferantTest(TestCase):
	def test_joins_the_ten_parts_of_the_bilanz_as_the_handbook_writes_them(self):
		"""The example of Kap. 9.7.1 separates the parts with a semicolon and a blank."""
		self.assertEqual(
			nutzdaten_datenlieferant(
				name="Beispiel GmbH",
				street="Hauptstraße",
				house_number="1",
				house_number_suffix="a",
				address_supplement="Hinterhaus",
				postal_code="80331",
				city="München",
				country="Deutschland",
				phone="089 1234567",
				email="info@example.org",
			),
			ERSTELLER,
		)

	def test_keeps_the_place_of_a_part_that_is_missing_and_ends_without_a_blank(self):
		"""ERiC 44.3.6.0 refuses a DatenLieferant that ends with a blank (validation of Bilanz_6.9)."""
		self.assertEqual(
			nutzdaten_datenlieferant(
				name=" Beispiel GmbH ",
				street="Hauptstraße",
				house_number="1",
				postal_code="80331",
				city="München",
			),
			"Beispiel GmbH; Hauptstraße; 1; ; ; 80331; München; ; ;",
		)


class DeliverySchemaTest(TestCase):
	"""The DatenTeil of each Datenart in the TransferHeader that EricCreateTH writes from its description, against the
	schema of the whole delivery in the ERiC documentation 44.3.6.0."""

	def assert_valid(self, schema: etree.XMLSchema, document: bytes) -> None:
		if not schema.validate(etree.ElementTree(etree.fromstring(document))):
			self.fail(str(schema.error_log))

	def test_the_voranmeldung_and_form_ust_1_h_are_deliveries_of_the_ustva(self):
		schema = eric_schema.envelope_schema(2026)
		filer, created = examples.filer(), examples.CREATED
		for name, nutzdaten in (
			("Voranmeldung", ustva_xml.to_nutzdaten(filer, examples.voranmeldung(), created, "12345")),
			("USt 1 H", ust1h_xml.to_nutzdaten(filer, examples.anmeldung(), created, "12345")),
		):
			for testmerker in (True, False):
				with self.subTest(name=name, testmerker=testmerker):
					self.assert_valid(schema, delivery(datenteil(nutzdaten, HEADER), ustva(2026), testmerker))

	def test_the_zm_is_a_delivery_of_zmdo(self):
		schema = eric_schema.zm_envelope_schema()
		for testmerker in (True, False):
			with self.subTest(testmerker=testmerker):
				document = delivery(datenteil(zm_examples.nutzdaten(), ZM_HEADER), ZMDO, testmerker)
				self.assert_valid(schema, document)

	def test_the_erklaerungen_are_deliveries_of_elster_erklaerung(self):
		"""The Nutzdaten of the examples of the documentation, in the DatenTeil of a header of their Datenart."""
		for kind, example in (
			(ust(2026), "USt_2026.xml"),
			(kst(2025), "kst_2025_ok.xml"),
			(gewst(2025), "GewSt_2025.xml"),
		):
			with self.subTest(datenart=kind.version):
				document = etree.parse(
					str(eric_schema.erklaerung_directory(kind.name) / "Beispiele" / example)
				)
				((nutzdaten,),) = document.getroot().iter(
					"{http://www.elster.de/elsterxml/schema/v11}Nutzdaten"
				)
				empfaenger = nutzdaten.findtext(f"{{{kind.namespace}}}Vorsatz/{{{kind.namespace}}}StNr")[:4]
				header = replace(HEADER, datenart_version=kind.version, empfaenger=empfaenger)
				schema = eric_schema.erklaerung_envelope_schema(kind.name, kind.root, kind.year)
				for testmerker in (True, False):
					with self.subTest(testmerker=testmerker):
						text = etree.tostring(nutzdaten, encoding="unicode")
						self.assert_valid(schema, delivery(datenteil(text, header), kind, testmerker))

	def test_the_bilanz_is_a_delivery_of_elster_bilanz_with_the_datenlieferant_of_its_nutzdaten_header(self):
		"""ebilanz_000002.xsd, with a stand-in for the XBRL instance schema (eric_schema.bilanz_envelope_schema)."""
		document = etree.fromstring(eric_schema.bilanz_example("6.9"))
		((nutzdaten,),) = document.iter("{http://www.elster.de/elsterxml/schema/v11}Nutzdaten")
		text = etree.tostring(nutzdaten, encoding="unicode")
		for testmerker in (True, False):
			with self.subTest(testmerker=testmerker):
				self.assert_valid(
					eric_schema.bilanz_envelope_schema(),
					delivery(datenteil(text, BILANZ_HEADER), bilanz("6.9"), testmerker),
				)
