from dataclasses import replace
from unittest import TestCase
from xml.etree import ElementTree

from lxml import etree

from steuerbote.elster import ust1h_xml, ustva_xml
from steuerbote.elster.tests import eric_schema, examples, zm_examples
from steuerbote.eric.datenart import ZMDO, Datenart, ustva
from steuerbote.eric.header import ILLUSTRATION_HERSTELLER_ID, EnvelopeHeader, datenteil, problems
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

	def test_the_product_name_must_not_contain_elster_in_any_case(self):
		self.assertEqual(self.fields(replace(HEADER, produkt_name="Mein Elster")), ["ProduktName"])


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
